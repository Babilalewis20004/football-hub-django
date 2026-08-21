# Security Pipeline (DevSecOps)

This document describes `.github/workflows/security.yml` — the automated
security pipeline that runs on every feature-branch push, every Pull
Request targeting `main`, and every push to `main` (including merged PRs).
It complements, and doesn't replace, the point-in-time manual reviews in
`SECURITY_AUDIT_2026-08-10.md` and the CSP rollout notes in
`docs/security/csp/`.

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
├── dast-zap                  — OWASP ZAP baseline scan against the running app
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
image used by `docker-compose.prod.yml`. Both `trivy-image` steps pass
`scanners: vuln,misconfig` explicitly (matching `trivy-fs`), rather than
Trivy's image-scan default, which also runs secret detection. Verified
2026-08-16: without that scope, Trivy flags a HIGH-severity
`AsymmetricPrivateKey` inside `autobahn`'s own bundled source
(`site-packages/autobahn/wamp/cryptosign.py`) — an upstream dependency's
example/doctest key, not a project secret. Secret-scanning our own
source and full git history is already Gitleaks' job (§6); scanning for
secrets inside vendored third-party package internals is out of scope
here and just reproduces false positives like this one every time a
dependency ships an example key in its own code.

- **Failure policy (both jobs):** same two-pass pattern — a full,
  unfiltered SARIF report for visibility, then a gate scoped to
  `--severity CRITICAL,HIGH --ignore-unfixed`. `--ignore-unfixed` is a
  deliberate scope decision, not rule suppression: an unfixed finding has
  no patched version available anywhere in the dependency chain yet, so
  blocking merges on it doesn't lead anywhere actionable — it just makes
  the pipeline permanently red for reasons no PR can fix. Every finding
  (fixed or not, any severity) is still visible in the full report.

## 7a. DAST — OWASP ZAP baseline scan

Every other job in this pipeline analyzes source, dependencies, or a built
image *at rest*. `dast-zap` is the one job that starts the real
application and attacks it over HTTP the way an external client would —
it's the only place that would catch a purely runtime/config issue (e.g.
a missing security header, a cookie flag, actual reflected behavior)
rather than a static pattern in the code.

- **How the app is started:** the job brings up the same Postgres service
  container as `test`, then runs the exact same startup sequence as
  `docker/entrypoint.sh` (`migrate` → `setup_roles` →
  `backfill_user_roles` → `collectstatic`) before starting `daphne` on
  `127.0.0.1:8000` in the background. `DEBUG=False`, matching production
  (a `DEBUG=True` app would itself trip ZAP's debug-mode alert).
- **Deliberately scanned over plain HTTP:** unlike `django-security-checks`,
  this job does **not** set `SECURE_SSL_REDIRECT`/`SESSION_COOKIE_SECURE`/
  `CSRF_COOKIE_SECURE`. This runner has no TLS termination in front of it —
  turning those on here would make the app redirect every request ZAP
  sends (or silently drop the CSRF cookie on every form submission),
  collapsing the crawl to effectively one page. Scanning a locally-started
  app over HTTP is the standard way to run baseline DAST in CI; the
  HTTPS-specific settings themselves are already covered by
  `django-security-checks` (§2).
- **Scanner:** `ghcr.io/zaproxy/zaproxy:stable`'s `zap-baseline.py`
  (passive scan + spider, not the more intrusive Full Scan), run directly
  via `docker run --network host` so the ZAP container can reach the app
  listening on the runner's `localhost:8000`.
- **Failure policy:** same two-pass pattern as Bandit/Semgrep/Trivy. The
  first pass (`-I`, no rules file) never fails and writes an unfiltered
  JSON + HTML report, uploaded as the `zap-report` workflow artifact — ZAP
  has no SARIF exporter, same situation as pip-audit (§8), so this is an
  artifact rather than a Security-tab upload. The second pass adds
  `-c .zap/rules.tsv`, which reclassifies a small, individually-verified
  set of high-risk alert types (reflected/persistent XSS, SQL injection,
  remote OS command injection, path traversal, remote file inclusion) as
  `FAIL`; combined with `-I` (which suppresses failing on the default
  `WARN` classification everything else gets), the gate only fires on
  those specific high-risk categories — not on every informational/
  low-risk finding. See `.zap/rules.tsv`'s header for exactly which rule
  IDs are covered and how they were verified.
- **Tune after the first real run:** the starter rule set in
  `.zap/rules.tsv` is intentionally conservative. Review the first few
  `zap-report` artifacts for alert types this app actually surfaces and
  expand the file from there, the same way Bandit's B105/B106 skip was
  added only after reading every hit (§3).

## 8. SARIF / GitHub Security tab integration

Bandit, Semgrep, Gitleaks, and both Trivy jobs upload SARIF results via
`github/codeql-action/upload-sarif`, each tagged with a distinct
`category` (`bandit`, `semgrep`, `gitleaks`, `trivy-fs`, `trivy-image`) so
results from different tools don't overwrite each other in the
repository's **Security → Code scanning alerts** tab. `security-events:
write` is granted only on those specific jobs, not workflow-wide.

pip-audit and the ZAP baseline scan (`dast-zap`) have no SARIF exporter,
so their reports are uploaded as workflow artifacts instead (Actions →
the run → **Artifacts** — `pip-audit-report` and `zap-report`
respectively) — per the principle of retaining useful output when SARIF
isn't available rather than dropping the finding. Bandit's SARIF and
Trivy's SARIF are *also* uploaded as artifacts in addition to Code
Scanning, for anyone who wants the raw file without going through the
Security tab.

**Prerequisite: GitHub code scanning must be enabled on the repository.**
`upload-sarif` uploads to **Security → Code scanning alerts**, a GitHub
feature that requires either a public repository (free) or GitHub
Advanced Security enabled on a private one (paid, org/enterprise
setting). Without one of those, every `upload-sarif` step fails with
"Code scanning is not enabled for this repository" — which is exactly
what made `bandit`, `semgrep`, `gitleaks`, `trivy-fs`, and `trivy-image`
all fail in this repo's initial PR run (diagnosed 2026-08-16), while
`test`, `django-security-checks`, and `pip-audit` — none of which call
`upload-sarif` — passed. It was not a scanner finding in any of the five
jobs: Bandit, Semgrep, and Gitleaks (full history) all independently
verified clean locally that same day. This repo's fix was to make the
repository public rather than change the workflow; the `if: always()`
SARIF steps have no other prerequisite and will succeed as soon as code
scanning is available. If this repo is ever made private again without
GHAS, the same failure will return on all five jobs simultaneously —
that pattern (only SARIF-uploading jobs red, artifact uploads and
severity-gate logs otherwise clean) is the signature to check for before
assuming a real regression.

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
| `DAST - OWASP ZAP Baseline` | **Required** (after first real run confirms `.zap/rules.tsv`, per §7a's note) | Only fails on the verified high-risk alert types in `.zap/rules.tsv` |

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
| ZAP baseline (DAST) | The high-risk alert types listed in `.zap/rules.tsv` (XSS, SQLi, command injection, path traversal, RFI) | Everything else (default `WARN`/`INFO`) | Conservative, individually-verified starter set — see §7a |

**If a scanner finds something new:** treat it as a real regression to
fix, not a config knob to loosen. If a finding is later confirmed to be a
false positive, document *why* at the point of suppression (as done for
Bandit's B105/B106 above) rather than disabling the check globally or
adding a blanket `continue-on-error`.

## 11. Existing / pre-existing findings (as of 2026-08-16)

These are recorded for transparency, not hidden by the pipeline's
configuration:

| Finding | Source | Status | Why it doesn't block CI |
|---|---|---|---|
| `django-ckeditor` bundles CKEditor 4, EOL with unfixed security issues (`ckeditor.W001`) | `manage.py check --deploy` | Open, tracked in `SECURITY_AUDIT_2026-08-10.md` §4.4 and `docs/README.md` | Structural — no config fix exists; requires migrating to a maintained editor. Django's own default `check` gate only fails on `ERROR`-level issues, and this is `WARNING`-level. |
| `SECURE_HSTS_INCLUDE_SUBDOMAINS` / `SECURE_HSTS_PRELOAD` not enabled (`security.W005`/`W021`) | `manage.py check --deploy` (CI-simulated production posture) | Open — not yet wired to a setting in `config/settings.py` | Operational/policy decision (whether *all* subdomains should be HTTPS-only) that belongs to the project owner, not something this pipeline should silently force by editing `settings.py` |
| 6 outdated-but-not-vulnerable direct dependencies (django-crispy-forms, crispy-bootstrap5, django-ckeditor, gunicorn, whitenoise, psycopg2-binary) | `SECURITY_AUDIT_2026-08-10.md` §2.4 | Informational | No known CVEs; pip-audit correctly doesn't flag these — routine maintenance, not a security gate concern |
| `AsymmetricPrivateKey` in `autobahn/wamp/cryptosign.py` | Trivy image scan, default scanners | Resolved by scope, not suppression | See §7 — an upstream dependency's own bundled example key; `trivy-image` now scopes to `vuln,misconfig` (matching `trivy-fs`) instead of scanning secrets inside vendored package internals |
| `CVE-2026-8643` — pip < 26.1.2 path traversal via malicious wheel entry-point name (installed: 25.0.1, fixed: 26.1.2) | Trivy image scan (Code scanning alert #227) | Open, tracked here | MEDIUM severity — correctly below this pipeline's CRITICAL/HIGH merge-gate threshold (§10), so it reports without blocking, as designed. It's also the base `python:3.12-slim` image's own bundled system pip (`/usr/local/lib/python3.12/site-packages/pip-25.0.1`), never the app's pip in `/opt/venv`, and never invoked at runtime — the entrypoint only runs the app itself, not `pip install` — so real exploitability is negligible even though the CVE is genuine. Revisit if a future Debian/`python:3.12-slim` refresh bundles a patched pip for free, or if this ever needs to move above MEDIUM. |

pip-audit, Bandit, Gitleaks, and Trivy all reported **zero** *project*
findings when last verified locally (2026-08-16) — see each tool's
section above for the exact commands used to confirm this. The
`autobahn` key and pip CVE above both came from third-party/base-image
code, not this project's own source or history.

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
  image --scanners vuln,misconfig football-hub:ci

# ZAP baseline (DAST) — requires Docker, and the app already running
# locally (e.g. `python manage.py runserver` or `docker compose up`) on
# port 8000. On Linux, --network host works as in CI; on macOS/Windows
# Docker Desktop, use http://host.docker.internal:8000 as the target
# instead and drop --network host.
docker run --rm --network host -v "${PWD}:/zap/wrk:rw" \
  -t ghcr.io/zaproxy/zaproxy:stable \
  zap-baseline.py -t http://localhost:8000 -I -c /zap/wrk/.zap/rules.tsv
```

**Local environment note (Windows):** if `pip-audit`/`bandit`/`docker
build`/`trivy` fail with `SSLCertVerificationError`/`x509: certificate
signed by unknown authority` against `pypi.org`/`api.osv.dev`/
`mirror.gcr.io` on a Windows dev machine, it's typically a local
TLS-inspecting proxy/AV product whose CA isn't in the relevant tool's
trust store (already documented in `SECURITY_AUDIT_2026-08-10.md` §2.3).
`pip install pip-system-certs` bridges Python (pip-audit, Bandit) to the
OS trust store; Docker/Trivy don't pick that up the same way, so a
build/scan can still fail locally behind this kind of proxy even though
it succeeds on GitHub-hosted runners, which sit outside it entirely —
this is a local reproduction limitation, not a pipeline defect.

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
