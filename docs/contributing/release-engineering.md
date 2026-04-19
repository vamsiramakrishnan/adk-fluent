# Release engineering

adk-fluent ships two packages from one monorepo — `adk-fluent` on PyPI
and `adk-fluent-ts` on npm. Releases are symmetric: same version
string, same tag, same workflow shape, same cadence. This page covers
how the pipeline is wired and how to cut a release.

## Architecture at a glance

```
┌──────────┐          ┌──────────────────────────┐
│ VERSION  │ ◀─────── │ single source of truth   │
│  0.14.1  │          │ (repo root, plain semver)│
└────┬─────┘          └──────────────────────────┘
     │
     ├──▶ python/src/adk_fluent/_version.py   ◀── docs/conf.py reads from here
     └──▶ ts/package.json
```

The ``shared/scripts/release/`` module owns propagation. Everything
else — the justfile recipes, the CI workflows, the docs build — reads
from these three files.

### GitHub Actions layout

```
release.yml                      ← orchestrator; thin dispatcher
 ├─ plan (preflight, resolve target)
 ├─ python-pypi     uses ./_publish-python.yml  (target=pypi)
 ├─ python-testpypi uses ./_publish-python.yml  (target=testpypi)
 ├─ ts-npm          uses ./_publish-npm.yml     (target=npm)
 ├─ ts-npm-dry      uses ./_publish-npm.yml     (target=npm-dry-run)
 └─ github-release  (tag push only) attaches dist artifacts

_publish-python.yml              ← reusable; build → inspect → publish
_publish-npm.yml                 ← reusable; build → inspect → publish
```

Both reusable workflows have the same three stages — ``build``,
``inspect``, ``publish`` — so a failure in one is debugged the same
way you debug the other.

## Cutting a release

All commands live in ``justfile.release`` and are named ``rel-*``.

### Normal flow (patch, minor, major)

```console
$ just rel-prepare minor       # bumps, syncs, promotes [Unreleased], commits
$ git push origin master
$ just rel-tag                 # creates + pushes v0.15.0 → CI publishes
```

### Dry-run

Rehearse the whole pipeline against TestPyPI + ``npm pack``:

```console
$ just rel-bump patch          # stage the new version locally
$ just rel-preflight           # verify readiness
$ just rel-dry-run             # dispatches the CI workflow with target=dry-run
```

Because the dry-run targets are TestPyPI and ``npm-dry-run`` (a pack,
no publish), it is safe to run repeatedly. If it fails, fix forward
without publishing.

### Individual steps

| command | what it does |
|---|---|
| ``just rel-version``            | print the canonical version |
| ``just rel-status``             | show VERSION vs consumers + changelog state |
| ``just rel-bump LEVEL``         | bump + propagate to ``_version.py`` and ``package.json`` |
| ``just rel-sync [X.Y.Z]``       | propagate current (or given) VERSION to consumers |
| ``just rel-preflight``          | lint the release state (versions agree, changelog has entry, tag free, tree clean) |
| ``just rel-preflight-strict``   | same, but treats warnings as failures (used in CI) |
| ``just rel-prepare LEVEL``      | bump + sync + promote [Unreleased] + commit |
| ``just rel-dry-run``            | dispatch ``release.yml`` with ``target=dry-run`` |
| ``just rel-tag``                | ``git tag -a vX.Y.Z`` + push |
| ``just rel-publish-python``     | local escape hatch — prefer CI |
| ``just rel-publish-npm``        | local escape hatch — prefer CI |

Old names (``just version``, ``just bump``, ``just release``,
``just release-tag``) keep working as aliases.

## Preflight checks

``just rel-preflight`` runs a short list of non-destructive checks and
prints ``[ok]`` / ``[warn]`` / ``[fail]`` per line. Checks are defined
in ``shared/scripts/release/preflight.py:CHECKS``.

Current checks:

- **versions**        — VERSION, ``_version.py``, and ``package.json`` all agree.
- **changelog**       — entry for the current version exists, or ``[Unreleased]`` is populated and will be promoted on prepare.
- **python/pyproject** — ``python/pyproject.toml`` present.
- **ts/package.json** — TS package file present and has a ``"files"`` allowlist.
- **tag**             — ``vX.Y.Z`` is free locally and on ``origin``.
- **tree**            — working tree is clean.

Add a check by appending a function to ``CHECKS``; it runs in CI via
``--strict``.

## Supply-chain hygiene

- **PyPI Trusted Publishing**: no long-lived tokens. The ``publish-pypi``
  environment on GitHub is wired to the project on pypi.org (and
  test.pypi.org) via OIDC. ``attestations: true`` produces PEP 740
  provenance.
- **npm provenance**: ``npm publish --provenance`` emits a sigstore
  bundle and records the GitHub Actions run that produced the tarball.
  Requires a public repo and ``id-token: write`` — both in place.
- **GitHub Release assets**: every tagged release attaches the wheel,
  sdist, and npm tarball. Users can pin against a checksummed asset
  instead of (or in addition to) the registry.

## Adding a new distribution target

Say you want to publish a container image or a Homebrew formula.
Because the orchestrator is a thin dispatcher, the cost of adding a
target is one reusable workflow plus two lines in ``release.yml``:

```yaml
# .github/workflows/_publish-docker.yml  (new)
on: { workflow_call: { inputs: { version: { required: true, type: string } } } }
jobs:
  build:    { ... }
  publish:  { needs: [build], ... }
```

```yaml
# release.yml  (orchestrator)
docker:
  needs: [plan]
  if: needs.plan.outputs.publish-docker == 'true'
  uses: ./.github/workflows/_publish-docker.yml
  with: { version: ${{ needs.plan.outputs.version }} }
```

Add ``publish-docker`` to the ``plan`` job's output-resolving script
and a matching ``--target docker`` option on the dispatch input. The
``rel-*`` recipes need no changes — they are language-neutral.

## Debugging a failed release

| symptom | likely cause | fix |
|---|---|---|
| ``tag v0.X.Y already exists`` | you tagged but the CI run didn't publish, so you retried. | delete the tag, ``just rel-sync``, re-tag. |
| ``NPM_TOKEN not set on the 'npm' environment`` | token lives on a different environment or only at the repo scope. | re-add the secret under *Settings → Environments → npm → Environment secrets*. |
| ``tarball missing dist/index.js`` | ``ts/package.json`` ``files`` field drifted or build didn't run. | the reusable npm workflow runs ``npm run build`` before pack; check the build log. |
| ``twine check`` fails | long description has malformed RST/Markdown. | open the offending dist file locally (``uv build`` then read the metadata). |
| ``Trusted publishing failed``: environment not configured on PyPI | forgot to register the workflow on pypi.org. | Add a *pending publisher* under the project's *Publishing* settings on pypi.org. |

When in doubt, re-dispatch ``release.yml`` with
``target=dry-run`` first. It exercises the same code path without
touching production registries.
