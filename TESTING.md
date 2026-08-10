# Testing

## Pytest setup

This project runs its existing Django `TestCase` suite through `pytest` via `pytest-django`, alongside (not instead of) `python manage.py test`.

- Packages: `pytest==9.1.1`, `pytest-django==4.14.0`, `pytest-cov==7.1.0` (see `requirements.txt`)
- Config: [pytest.ini](pytest.ini) — sets `DJANGO_SETTINGS_MODULE = config.settings` and test discovery for `tests.py`, `test_*.py`, `*_tests.py`
- Run the suite: `python -m pytest -v`
- Run with coverage: `python -m pytest --cov=blog --cov-report=term-missing`

As of the last run, both runners agree on **90 tests**, all passing.

## Current coverage status (`blog` app)

Last measured with `python -m pytest --cov=blog --cov-report=term-missing`:

**Overall: 83% (766 statements, 129 missed)**

Most modules sit at or near 100%. The exceptions:

| File | Coverage |
|---|---|
| `blog/views/comments.py` | 0% |
| `blog/mixins.py` | 0% |
| `blog/services/comments.py` | 17% |
| `blog/views/interactions.py` | 43% |
| `blog/views/posts.py` | 56% |

These gaps are pre-existing (not introduced by the pytest setup itself) and are tracked below.

## End-of-Project Test Coverage Backlog

> **These gaps are being deferred intentionally, not forgotten.** The pytest/pytest-django setup is in place and passing; the work below is scoped test-writing for under-covered production code. This section exists specifically so it doesn't get lost — it must be revisited and closed out **before the project is considered finished**.

| File | Current coverage | Priority | What needs to be tested | Status |
|---|---|---|---|---|
| `blog/views/comments.py` | 0% | High | Comment view(s) — posting, editing/deleting comments, permission checks, error paths | Pending |
| `blog/mixins.py` | 0% | High | Whatever access-control/behavior the mixins enforce (currently exercised only incidentally, if at all) | Pending |
| `blog/services/comments.py` | 17% | Medium | Comment service logic beyond the single currently-covered path — creation, validation, edge cases | Pending |
| `blog/views/interactions.py` | 43% | Medium | Like/bookmark/interaction endpoints not yet hit by tests (lines 17-37, 42-65) | Pending |
| `blog/views/posts.py` | 56% | High | Post CRUD edge cases, permission branches, and error handling not yet covered (largest single gap by line count) | Pending |

### End-of-project checklist

- [ ] Test `blog/views/comments.py`
- [ ] Test `blog/mixins.py`
- [ ] Improve coverage for `blog/services/comments.py`
- [ ] Improve coverage for `blog/views/interactions.py`
- [ ] Improve coverage for `blog/views/posts.py`
- [ ] Run the complete pytest suite (`python -m pytest -v`)
- [ ] Run coverage with `--cov=blog --cov-report=term-missing`
- [ ] Review all remaining uncovered statements
- [ ] Confirm no important production code remains unintentionally untested
- [ ] Target at least 90% overall coverage if practical
