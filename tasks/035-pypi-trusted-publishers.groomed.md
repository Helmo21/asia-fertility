# PyPI publish via Trusted Publishers (OIDC, no secrets)

Status: pending
Tags: `publishing`, `pypi`, `trusted-publishers`, `oidc`, `release`
Depends on: #034
Blocks: #036

## Scope

Add the GitHub Actions workflow that publishes `fertiscope` to PyPI when a `v*` tag is pushed. Use **Trusted Publishers** (OIDC, configured PyPI-side) — no PyPI API tokens stored as GitHub secrets. Also document the release playbook.

### Files to create

- `.github/workflows/publish.yml`
- `RELEASE.md` — step-by-step release playbook.

### Files to modify

- `pyproject.toml` — bump version to `0.3.0` when releasing v0.3.

### Interface and contract

`.github/workflows/publish.yml`:

```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'
  workflow_dispatch:

jobs:
  build:
    name: Build wheel + sdist
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Verify version matches tag
        run: |
          PROJECT_VERSION=$(uv run --extra dev python -c "import fertiscope; print(fertiscope.__version__)")
          TAG_VERSION="${GITHUB_REF_NAME#v}"
          if [ "$PROJECT_VERSION" != "$TAG_VERSION" ]; then
            echo "Mismatch: pyproject.toml version=$PROJECT_VERSION, tag=$TAG_VERSION"
            exit 1
          fi
      - run: uv build
      - name: Validate built artifacts
        run: |
          uv pip install --system twine
          twine check dist/*
      - uses: actions/upload-artifact@v4
        with:
          name: dist
          path: dist/

  publish-testpypi:
    name: Publish to TestPyPI
    needs: build
    runs-on: ubuntu-latest
    if: ${{ !contains(github.ref_name, 'rc') == false || contains(github.ref_name, 'rc') }}
    environment:
      name: testpypi
      url: https://test.pypi.org/p/fertiscope
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://test.pypi.org/legacy/

  publish-pypi:
    name: Publish to PyPI
    needs: build
    runs-on: ubuntu-latest
    if: ${{ !contains(github.ref_name, 'rc') }}
    environment:
      name: pypi
      url: https://pypi.org/p/fertiscope
    permissions:
      id-token: write
    steps:
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - uses: pypa/gh-action-pypi-publish@release/v1

  github-release:
    name: GitHub Release
    needs: publish-pypi
    runs-on: ubuntu-latest
    permissions:
      contents: write
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: dist
          path: dist/
      - name: Create GitHub Release
        uses: softprops/action-gh-release@v2
        with:
          files: |
            dist/*.whl
            dist/*.tar.gz
          generate_release_notes: true
```

`RELEASE.md`:

```markdown
# Release playbook

## One-time setup

### Trusted Publishers on PyPI

1. Create the project on PyPI: https://pypi.org/manage/account/publishing/
2. Add a Trusted Publisher with:
   - Owner: `dangpleo-ctrl`
   - Repository: `fertiscope`
   - Workflow filename: `publish.yml`
   - Environment name: `pypi`
3. Same on TestPyPI with environment `testpypi`.

### GitHub Environments

Create two environments under repo Settings → Environments:
- `pypi` (production)
- `testpypi` (staging)

Optional: protect the `pypi` environment with required reviewers.

## Per-release steps

1. Bump version in `src/fertiscope/__init__.py` and `pyproject.toml`.
2. Bump `version` and `date-released` in `CITATION.cff`.
3. Update `CHANGELOG.md` (if present) or use auto-generated GH release notes.
4. Commit: `git commit -am "release v0.3.0"`.
5. Tag: `git tag v0.3.0`.
6. Push: `git push origin main --tags`.
7. The publish workflow runs automatically:
   - Verifies tag matches `pyproject.toml` version.
   - Builds wheel + sdist.
   - `twine check` validates metadata.
   - Publishes to TestPyPI (uses `testpypi` environment, OIDC).
   - Publishes to PyPI (uses `pypi` environment, OIDC).
   - Creates a GitHub Release with wheel + sdist artifacts.

## Release candidates

For pre-release validation:

```bash
git tag v0.3.0rc1
git push origin v0.3.0rc1
```

`rc` in tag name skips production PyPI publish; only TestPyPI runs.

## Yanking a release

```bash
pip install pypi-yank
pypi-yank fertiscope 0.3.0
```

Or via PyPI web UI (Project → Manage → Yank release).

## Smoke-test after release

```bash
python -m venv /tmp/fertiscope_test
source /tmp/fertiscope_test/bin/activate
pip install "fertiscope[oai]==0.3.0"
fertiscope --version            # → fertiscope 0.3.0
fertiscope reproduce             # → ✓ table renders in < 30s
```
```

### Notes

- **Trusted Publishers (OIDC)** are the only safe way to publish in 2026. Stored API tokens get leaked.
- The `environment:` block ties the workflow to a GitHub Environment, which is required for OIDC to work with PyPI.
- The version-match check prevents accidental "tag v0.3.0 but pyproject says 0.2.5" publishing.
- TestPyPI publish runs for ALL tag pushes (including rc). Prod PyPI skips rc tags.
- `softprops/action-gh-release@v2` is the maintained GitHub release action.

## Acceptance Criteria

- [ ] `.github/workflows/publish.yml` valid YAML; passes GitHub's actions linter.
- [ ] Workflow has 4 jobs: build, publish-testpypi, publish-pypi, github-release.
- [ ] Both publish jobs use `id-token: write` permission (OIDC).
- [ ] Version-match guard exists and fails CI on mismatch.
- [ ] `RELEASE.md` documents one-time setup + per-release steps.
- [ ] Pushing `v0.3.0` (after PyPI Trusted Publisher setup) results in `fertiscope==0.3.0` on PyPI.
- [ ] `pip install fertiscope==0.3.0` works on a clean venv.
- [ ] `fertiscope --version` prints `0.3.0`.
- [ ] GitHub Release created with attached wheel + sdist.
- [ ] No PyPI API tokens stored anywhere in repo or GitHub secrets.

## User Stories

### Story: Maintainer ships v0.3.0

1. `git tag v0.3.0 && git push --tags`.
2. CI runs: builds, validates, publishes to TestPyPI (OIDC), publishes to PyPI (OIDC), creates GitHub Release.
3. Takes ~3 minutes total.
4. Maintainer never copies a PyPI token.

### Story: User installs from PyPI

1. `pip install fertiscope==0.3.0`.
2. Works on clean Ubuntu, macOS, Windows.
3. `fertiscope --version` matches expected.

### Story: Drift caught by version-match guard

1. Maintainer forgot to bump `pyproject.toml`.
2. CI runs on tag `v0.3.0`.
3. Step "Verify version matches tag" fails with diff.
4. Maintainer fixes, retags, retries.

---

Blocked by: #034
