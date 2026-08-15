# Security Pipeline (DevSecOps)

This document describes `.github/workflows/security.yml` — the automated
security pipeline that runs on every feature-branch push, every Pull
Request targeting `main`, and every push to `main` (including merged PRs).
It complements, and doesn't replace, the point-in-time manual reviews in
`SECURITY_AUDIT_2026-08-10.md` and the CSP rollout notes in
`Content Security policy Docs/`.

## 1. When it runs

```yaml
on:
  push:
    branches: ["**"]      # every branch, including feature branches
  pull_request:
    branches: [main]      # every PR targeting main
```

Because `push` matches every branch and a push to `main` (including a
merged PR's merge commit) is itself a push, all three of the required
trigger scenarios are covered by this one `on:` block:

1. Feature-branch commits/pushes
2. Pull Requests targeting `main`
3. Pushes to `main`, including merges

Runs on the same branch/PR that are superseded by a newer push are
automatically cancelled (`concurrency` block) so scans don't queue up.

## 2. Pipeline architecture

```text
Security Pipeline (.github/workflows/security.yml)
│
├── test                      — pytest / pytest-django (existing suite, unmodified)
├── django-security-checks    — python manage.py check --deploy
├── bandit                    — SAST (Python/Django)
├── semgrep                   — SAST (Python/Django/secrets rulesets)
├── pip-audit                 — dependency vulnerability scan
├── gitleaks                  — secret scan (full git history)
├── trivy-fs                  — filesystem vulnerability + IaC/Dockerfile misconfig scan
├── trivy-image                — builds the Dockerfile and scans the resulting image
└── security-gate             — aggregates the above into one required status check
```

All jobs run in parallel and are independent — a failure in one doesn't
block the others from reporting, which keeps feedback fast and each
failure's cause unambiguous. `security-gate` (`needs: [...]`, `if: always()`)
rolls every job's result into a single named check for convenience; the
individual jobs remain visible and can also be required directly (see
§9).

Permissions follow least privilege: the workflow-level default is
`contents: read`; only the jobs that upload SARIF results elevate to
`security-events: write`, and only for the duration of that job.

## 3. SAST — Bandit

- **What it scans for:** Python/Django source-level security issues —
  SQL injection, `eval`/`exec` use, hardcoded credentials, insecure
  deserialization, weak crypto, `assert` in production code paths, etc.
- **Scope:** the whole repository, minus `venv/`, `.venv/`, `staticfiles/`,
  `media/`, `logs/`, and `*/migrations/` (config lives in
  `pyproject.toml`'s `[tool.bandit]` table, shared by CI and local runs).
- **Known false positive, documented and skipped:** `B105`/`B106`
  ("possible hardcoded password") fire on password-*shaped* string
  literals in test fixtures — e.g. `users/tests.py`'s
  `"correct-horse-battery-staple"` login fixture. These are not real
  secrets (verified by reading every hit before adding the skip); B105/B106
  are skipped project-wide in `pyproject.toml` rather than scattering
  `# nosec` comments through test files.
- **Failure policy:** two passes. The first (`--exit-zero`) always
  succeeds and produces a full-fidelity SARIF report uploaded to the
  GitHub Security tab and as a workflow artifact, so every finding —
  including low-severity ones — stays visible for triage. The second pass
  (`--severity-level medium --confidence-level medium`) is the actual
  merge gate: it fails the job on any medium-or-higher severity finding
  with medium-or-higher confidence.
- **Current status (verified locally, 2026-08-15):** 0 findings at any
  severity across ~4,900 lines scanned.

## 4. SAST — Semgrep

- **What it scans for:** a second, independently-maintained ruleset
  layer — `p/security-audit`, `p/python`, `p/django`, and `p/secrets`
  (Semgrep Registry rulesets), covering OWASP-style issues, Django-specific
  anti-patterns (e.g. raw SQL, unsafe `mark_safe`/`format_html` use,
  missing `@login_required`), and secondary secret-pattern detection.
- **Scope:** whole repository, explicitly excluding `venv`, `.venv`,
  `node_modules` (not currently present, excluded defensively),
  `staticfiles`, `media`, `logs`, and `*/migrations/*`.
- **Failure policy:** same two-pass pattern as Bandit — an unfiltered
  SARIF report for visibility, then a gate restricted to `--severity ERROR`
  (Semgrep's highest severity band) via `--error`. INFO/WARNING findings
  are visible in the Security tab but don't block merges.
- **Note:** Semgrep has no official native Windows build, so this job's
  exact behavior couldn't be executed on the Windows machine this pipeline
  was built on — the CLI flags are verified against Semgrep's documented,
  stable interface, and the job runs on `ubuntu-latest` in GitHub Actions
  where Semgrep is fully supported. Review its first real run's output
  before relying on it as a required check.

## 5. Dependency scanning — pip-audit

- **What it scans for:** known CVEs/advisories (via PyPA's advisory
  database and OSV) affecting exact pinned versions in `requirements.txt`
  and `requirements-dev.txt` (the latter starts with `-r requirements.txt`,
  so one scan covers production and dev/test dependencies together).
- **Failure policy:** pip-audit's own default — fail if *any* known
  vulnerability is found. No severity filtering is applied; unlike SAST
  tools, a dependency scanner's job is binary (vulnerable pin or not), so
  there's no "low-severity noise" class to filter out the way there is for
  Bandit/Semgrep.
- **Current status (verified locally, 2026-08-15):** 0 known
  vulnerabilities. `SECURITY_AUDIT_2026-08-10.md` documents the prior
  remediation that got here (Django 5.2.3→5.2.17 fixed 31 advisories,
  Pillow 11.2.1→12.3.0 fixed 19). This pipeline is what keeps that at zero
  going forward instead of only being caught at the next manual audit.
- **Report format:** JSON (no official SARIF exporter exists for
  pip-audit), uploaded as a workflow artifact — see §8.

## 6. Secret scanning — Gitleaks

- **What it scans for:** API keys, passwords, tokens, Django
  `SECRET_KEY`-shaped values, database connection strings, cloud
  credentials, Telegram bot tokens (`\d+:[A-Za-z0-9_-]{35}` pattern),
  private key blocks, and Gitleaks' broader built-in rule set.
- **Scope:** full git history (`fetch-depth: 0`), not just the current
  working tree — a secret committed and later deleted is still caught,
  because it's still reachable in the repository's object history.
- **Log safety:** run with `--redact`, so matched secret *values* are
  never written to workflow logs, the SARIF report, or the uploaded
  artifact — only the file path, line number, and rule ID are.
- **`.env` status: verified clean.** `.env` is listed in `.gitignore`
  and is **not** tracked by git (`git ls-files` confirms only
  `.env.example` is tracked; `git log --all --full-history -- .env`
  returns nothing). No remediation was needed. If this ever changes,
  Gitleaks' full-history scan is exactly the mechanism that would catch
  it — see §10 for what to do if it ever fires.
- **Failure policy:** Gitleaks' own default — exit non-zero the moment
  any rule matches. Secret detection is binary; there's no meaningful
  "severity" tier to filter on the way SAST tools have.

## 7. Container/filesystem scanning — Trivy

Two separate jobs, matching the two distinct things Trivy checks:

**`trivy-fs`** — scans the checked-out repository filesystem for
(a) dependency vulnerabilities (a second, independent feed from
pip-audit — intentional overlap for defense in depth, not duplicated
effort for its own sake) and (b) Dockerfile/Compose misconfigurations
(e.g. running as root, missing `USER`, `ADD` vs `COPY`). Directories like
`venv/`, `staticfiles/`, and `media/` never need explicit exclusion here:
they're gitignored, so a fresh Actions checkout never contains them in
the first place.

**`trivy-image`** — builds the project's actual `Dockerfile`
(`docker build -t football-hub:ci .`, never pushed to any registry) and
scans the resulting image for OS-package and language-dependency
vulnerabilities. This is the same multi-stage, non-root (`USER appuser`)
image used by `docker-compose.prod.yml`.

- **Failure policy (both jobs):** same two-pass pattern — a full,
  unfiltered SARIF report for visibility, then a gate scoped to
  `--severity CRITICAL,HIGH --ignore-unfixed`. `--ignore-unfixed` is a
  deliberate scope decision, not rule suppression: an unfixed finding has
  no patched version available anywhere in the dependency chain yet, so
  blocking merges on it doesn't lead anywhere actionable — it just makes
  the pipeline permanently red for reasons no PR can fix. Every finding
  (fixed or not, any severity) is still visible in the full report.

## 8. SARIF / GitHub Security tab integration

Bandit, Semgrep, Gitleaks, and both Trivy jobs upload SARIF results via
`github/codeql-action/upload-sarif`, each tagged with a distinct
`category` (`bandit`, `semgrep`, `gitleaks`, `trivy-fs`, `trivy-image`) so
results from different tools don't overwrite each other in the
repository's **Security → Code scanning alerts** tab. `security-events:
write` is granted only on those specific jobs, not workflow-wide.

pip-audit has no SARIF exporter, so its JSON report is uploaded as a
workflow artifact instead (Actions → the run → **Artifacts**) — per the
principle of retaining useful output when SARIF isn't available rather
than dropping the finding. Bandit's SARIF and Trivy's SARIF are *also*
uploaded as artifacts in addition to Code Scanning, for anyone who wants
the raw file without going through the Security tab.

## 9. Pull Request gating and required status checks

This pipeline is designed to be usable as a GitHub branch-protection
requirement for `main`. Recommended configuration (**Settings → Branches
→ Branch protection rules → main → Require status checks to pass**):

| Check | Recommended | Why |
|---|---|---|
| `Security Pipeline Result` (the `security-gate` job) | **Required** | Single glance pass/fail; convenient minimum viable gate |
| `Test Suite (pytest)` | **Required** | Existing test suite must stay green |
| `Django Deployment Security Checks` | **Required** | Fails only on real `ERROR`-level Django system-check issues (see §11) |
| `SAST - Bandit` | **Required** | Currently 0 findings; any medium+ finding should block merge |
| `SAST - Semgrep` | **Required** (after first real run confirms the config, per §4's note) | Same reasoning |
| `Dependency Scan - pip-audit` | **Required** | Currently 0 known vulnerabilities |
| `Secret Scan - Gitleaks` | **Required** | Zero tolerance — any match should block merge |
| `Filesystem Scan - Trivy` | **Required** | Currently expected clean at CRITICAL/HIGH+fixable |
| `Container Scan - Trivy (Docker image)` | **Required** | Same |

Requiring the individual jobs (not just `security-gate`) gives clearer
per-tool failure attribution directly in the PR checks list, at the cost
of a longer required-checks list — either approach is valid; `security-gate`
exists specifically so a minimal single-check setup is also an option.

This workflow **never** merges, approves, or bypasses branch protection on
its own — it only reports pass/fail. The merge decision (code review +
these checks passing) stays entirely in GitHub's normal PR flow.

## 10. Severity and failure policy summary

| Tool | Blocks merge on | Doesn't block on | Rationale |
|---|---|---|---|
| pytest | Any test failure | — | Existing suite, unmodified |
| Django checks | `ERROR`-level system checks | `WARNING`-level (e.g. CKEditor EOL notice) | See §11 |
| Bandit | Medium+ severity, medium+ confidence | Low severity / low confidence | Filters known test-fixture false positives |
| Semgrep | `ERROR` severity | `WARNING`/`INFO` | Registry rulesets tier findings by real-world impact |
| pip-audit | Any known vulnerability | — | Binary signal; no filtering needed |
| Gitleaks | Any match | — | Binary signal; zero tolerance for secrets |
| Trivy (fs + image) | `CRITICAL`/`HIGH` **with a fix available** | `MEDIUM`/`LOW`, or unfixed findings | Blocking on unfixable findings has no remediation path |

**If a scanner finds something new:** treat it as a real regression to
fix, not a config knob to loosen. If a finding is later confirmed to be a
false positive, document *why* at the point of suppression (as done for
Bandit's B105/B106 above) rather than disabling the check globally or
adding a blanket `continue-on-error`.

## 11. Existing / pre-existing findings (as of 2026-08-15)

These are recorded for transparency, not hidden by the pipeline's
configuration:

| Finding | Source | Status | Why it doesn't block CI |
|---|---|---|---|
| `django-ckeditor` bundles CKEditor 4, EOL with unfixed security issues (`ckeditor.W001`) | `manage.py check --deploy` | Open, tracked in `SECURITY_AUDIT_2026-08-10.md` §4.4 and `docs/README.md` | Structural — no config fix exists; requires migrating to a maintained editor. Django's own default `check` gate only fails on `ERROR`-level issues, and this is `WARNING`-level. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` not enabled (`security.W005`/`W021`) | `manage.py check --deploy` (CI-simulated production posture) | Open — not yet wired to a setting in `config/settings.py` | Operational/policy decision (whether *all* subdomains should be HTTPS-only) that belongs to the project owner, not something this pipeline should silently force by editing `settings.py` |
| 6 outdated-but-not-vulnerable direct dependencies (django-crispy-forms, crispy-bootstrap5, django-ckeditor, gunicorn, whitenoise, psycopg2-binary) | `SECURITY_AUDIT_2026-08-10.md` §2.4 | Informational | No known CVEs; pip-audit correctly doesn't flag these — routine maintenance, not a security gate concern |

pip-audit, Bandit, Gitleaks, and Trivy all reported **zero** findings when
last verified locally (2026-08-15) — see each tool's section above for the
exact commands used to confirm this.

## 12. Running the same scans locally

All of these mirror exactly what CI runs (same config files, same
severity thresholds where applicable):

```bash
# Django deployment checks (uses your local .env — real dev values,
# so warnings will differ from CI's simulated-production-posture run)
python manage.py check --deploy

# Test suite
python -m pytest -v

# Bandit (SAST) — full report
pip install bandit bandit-sarif-formatter
bandit -c pyproject.toml -r .

# Semgrep (SAST)
pip install semgrep
semgrep scan --config p/security-audit --config p/python --config p/django --config p/secrets \
  --exclude venv --exclude .venv --exclude staticfiles --exclude media --exclude logs \
  --exclude "*/migrations/*" .

# pip-audit (dependency scan — covers requirements.txt + requirements-dev.txt)
pip install pip-audit
pip-audit -r requirements-dev.txt

# Gitleaks (secret scan, full git history) — requires Docker
docker run --rm -v "${PWD}:/repo" ghcr.io/gitleaks/gitleaks:v8.30.1 \
  detect --source /repo --redact -v

# Trivy (filesystem scan) — requires Trivy installed, or via Docker:
docker run --rm -v "${PWD}:/repo" aquasec/trivy:latest fs --scanners vuln,misconfig /repo

# Trivy (container image scan)
docker build -t football-hub:ci .
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
  image football-hub:ci
```

**Local environment note (Windows):** if `pip-audit`/`bandit` fail with
`SSLCertVerificationError` against `pypi.org`/`api.osv.dev` on a Windows
dev machine, it's typically a local TLS-inspecting proxy/AV product whose
CA isn't in Python's bundled trust store (already documented in
`SECURITY_AUDIT_2026-08-10.md` §2.3). `pip install pip-system-certs`
bridges Python to the OS trust store — a one-time local fix, not a
project dependency.

## 13. Caching

Python dependency installs are cached via `actions/setup-python`'s
built-in `cache: pip`, keyed on `requirements.txt`/`requirements-dev.txt`
(for jobs that install from those files) or on `.github/workflows/security.yml`
itself (for jobs like Bandit/Semgrep/pip-audit whose tool versions are
pinned directly in the workflow rather than in a requirements file — so
bumping a tool version there naturally invalidates its cache). No secrets
or generated reports are ever cached — only pip's wheel cache.

## 14. Python version

`3.12`, matching the Dockerfile's `python:3.12-slim` base image and the
local dev environment (`python --version` → `3.12.10`). No matrix is used
— the project targets exactly one Python version everywhere else, so a
matrix would test versions the project doesn't actually support.
