---
name: release
description: >
  MUST READ before cutting any release, triaging a failed release run,
  or editing anything under .github/workflows/release*.yml,
  shared/scripts/release/, justfile.release, or VERSION.
  adk-fluent dual-publish (PyPI + npm) release engineering — the hard-won
  nuances, gotchas that have actually broken production, and the exact
  checks to run before claiming a release "shipped".
allowed-tools: Bash, Read, Glob, Grep, WebFetch
---

# adk-fluent Release Engineering

> **A `Success` badge on the Release workflow does not mean the package
> shipped.** Always verify PyPI + npm directly before telling the user
> the release landed. See the "Verify after release" section.

## Architecture at a glance

Single source of truth: `VERSION` (plain semver at repo root).
Two consumers kept in sync automatically:

- `python/src/adk_fluent/_version.py`
- `ts/package.json`

Trigger: **a push to `master` that modifies any of those three files**.
No tags as triggers. No manual `gh release create`. The bump commit IS
the release signal.

The workflow graph:

```
release.yml (orchestrator)
  └── plan                 — decide skip / target, preflight --strict
  ├── python-pypi          → calls _publish-python.yml  (build + publish)
  ├── python-testpypi      → calls _publish-python.yml  (dry-run)
  ├── ts-npm               → calls _publish-npm.yml     (build + publish)
  ├── ts-npm-dry           → calls _publish-npm.yml     (pack only)
  └── tag-release          — creates v<VERSION> + GitHub Release
                             (gated: runs only if BOTH publishes succeed)
```

## Canonical flow

```
just rel-prepare minor    # bump + sync + promote changelog + commit
git push origin master    # CI takes over
```

That's it. Do not tag. Do not run `uv publish` locally. Do not edit
VERSION by hand. The `rel-prepare` recipe writes all three version files
atomically and promotes `[Unreleased]` → `[X.Y.Z]` in CHANGELOG.md in a
single commit titled `release: vX.Y.Z`.

## The nuances that have actually bitten us

### 1. PyPI Trusted Publisher must be registered against the REUSABLE workflow

This is the single most common failure mode. Observed failure:

```
invalid-publisher: valid token, but no corresponding publisher
  sub: repo:vamsiramakrishnan/adk-fluent:environment:pypi
```

**Why**: The OIDC `job_workflow_ref` claim resolves to the file that
actually invokes `pypa/gh-action-pypi-publish`. For adk-fluent, that file
is `_publish-python.yml`, NOT `release.yml`. PyPI compares the claim to
the registered publisher.

**Fix** (PyPI UI only — not scriptable from Claude):
- Project `adk-fluent` → *Publishing* → *Manage publishers*
- Workflow filename: **`_publish-python.yml`** (not `release.yml`)
- Environment: `pypi` (for prod) and `testpypi` (for dry-run)
- Owner: `vamsiramakrishnan`  Repo: `adk-fluent`

Register both environments. Symmetric requirement on TestPyPI.

**Why this hides in CI**: `tag-release` is gated on both publishes
succeeding, so a failed publish produces no tag. A second run on the
same VERSION then trips nothing (no idempotency skip, because no tag).
The top-level run can still render as `Success` because the outer
workflow file only has `plan` at its top level; sub-workflow failures
show inside the run detail, not in the runs list.

### 2. npm NPM_TOKEN lives on the `npm` environment, not repo secrets

`_publish-npm.yml` reads `NODE_AUTH_TOKEN` from `secrets.NPM_TOKEN` and
exits 1 with a clear error if missing. But: GitHub Environments secrets
and Repository secrets are distinct. Setting `NPM_TOKEN` as a repo
secret does NOT populate it in a job scoped to `environment: npm`.
Attach the token at **Settings → Environments → npm → Environment
secrets**. Symmetric rule for any future per-environment secret.

### 3. The `plan` job's skip logic has two independent triggers

Read `release.yml` lines 93–124 before changing anything here. Skip
fires when **either**:

- `v<VERSION>` already exists on origin (idempotency — safe re-pushes)
- `HEAD~1:VERSION == HEAD:VERSION` (path filter matched but VERSION did
  not actually change, e.g. a rebase that touched the file)

`fetch-depth: 2` is deliberate — without it, `git show HEAD~1:VERSION`
fails and the workflow reads `PREV=""`, which correctly falls through
to publish. Do not drop fetch-depth.

### 4. "1m30s Success" in the runs list is a publish failure tell

A healthy adk-fluent release takes **5–8 minutes** (build wheel + sdist,
build ts tarball, publish to PyPI with attestations, publish to npm
with provenance, download artifacts, tag + GitHub Release, attach
wheels + sdist + tgz). A run that completes in under 2 minutes means
`plan` ran, publish jobs failed fast, `tag-release` was skipped. Drill
in before celebrating.

### 5. `skip-existing: true` makes re-firing safe

`_publish-python.yml` sets `skip-existing: true` on `pypa/gh-action-pypi-publish`.
This means re-running a publish against a version already on PyPI is a
no-op, not a 400. So the safe recovery path for a failed publish is:

```
# After fixing the underlying config (trusted publisher, NPM_TOKEN, etc.)
gh workflow run release.yml -f target=pypi      # or npm, or all
```

Prefer this over pushing a no-op VERSION touch. A touch-commit would
force a version bump and pollute the CHANGELOG.

### 6. `tag-release` has `if: always() && ...` but requires `success`

```yaml
if: >-
  always() &&
  needs.plan.outputs.tag-on-success == 'true' &&
  needs.plan.outputs.skip == 'false' &&
  needs.python-pypi.result == 'success' &&
  needs.ts-npm.result == 'success'
```

`always()` exists so the job evaluates even when a dependency failed —
without it, the job would be skipped with result=skipped which is
ambiguous. With `always()`, we can explicitly require `success` on both
publishes. **Do not remove `always()`.**

### 7. Dispatch targets matter

`workflow_dispatch` accepts:

| target       | PyPI    | npm      | tag + GH Release |
|--------------|---------|----------|------------------|
| `all`        | publish | publish  | yes              |
| `dry-run`    | TestPyPI| pack     | no               |
| `pypi`       | publish | -        | yes              |
| `testpypi`   | TestPyPI| -        | no               |
| `npm`        | -       | publish  | yes              |
| `npm-dry-run`| -       | pack     | no               |

`pypi` and `npm` individually set `tag-on-success=true`. If only one
side needs republishing, you'll still get a tag — that's intended.

### 8. The preflight is environment-aware

`shared/scripts/release/preflight.py:check_tag_available` flips
semantics based on `GITHUB_REF`:

- On a branch push (including master): tag must NOT exist yet.
- On `refs/tags/vX.Y.Z`: tag MUST exist and match VERSION.

Never introduce a tag-push trigger without updating the preflight
counterpart; the two must stay symmetric.

### 9. The build job runs `just scan seed generate` before `uv build`

`_publish-python.yml` regenerates the builder surface from ADK source
during every publish. A stale seed.toml will ship stale builders.
`shared/scripts/release/preflight.py:check_python_build_ready` only
verifies `python/pyproject.toml` exists — it does not catch drift
between seeds and generated code. Run `just scan && just seed && just
generate` locally before `rel-prepare` on any release that follows
ADK-version bumps.

### 10. `just rel-prepare` commits to whatever branch you are on

The recipe has no branch guard. Running it on a topic branch commits a
`release: vX.Y.Z` commit onto that branch, not master. The CI trigger
won't fire until that commit is on master. Always `git checkout master
&& git pull` before `rel-prepare`.

## Verify after release — the checklist

Never tell the user "shipped" without checking all four:

```bash
# 1. Workflow run succeeded AND took > 3 minutes
#    (WebFetch https://github.com/vamsiramakrishnan/adk-fluent/actions/workflows/release.yml)

# 2. Tag exists on origin
git ls-remote --tags origin "v$(cat VERSION)"

# 3. PyPI has the new version
curl -s https://pypi.org/pypi/adk-fluent/json | jq -r '.info.version'

# 4. npm has the new version
curl -s https://registry.npmjs.org/adk-fluent-ts/latest | jq -r '.version'
```

All four must match `cat VERSION`. If any diverge, the release is NOT
complete — surface that to the user, do not claim success.

## Troubleshooting flowchart

**"The release workflow isn't running."**
→ Check the commit actually modified one of `VERSION`,
  `python/src/adk_fluent/_version.py`, or `ts/package.json`. A commit
  that only touches CHANGELOG.md won't fire the trigger.
→ Check the push landed on `master`, not a topic branch.

**"Workflow shows Success but PyPI has the old version."**
→ Run duration under 2 minutes → publish failed silently. Drill into
  `python-pypi / publish · pypi` job for the real error.
→ 99% of the time: trusted publisher misconfigured (see nuance #1).

**"I see `invalid-publisher` / `no corresponding publisher`."**
→ Nuance #1. Re-register PyPI publisher with filename
  `_publish-python.yml`.

**"npm publish fails with exit code 1."**
→ Most likely NPM_TOKEN missing on the `npm` environment (nuance #2),
  or 2FA-on-publish enabled on the npm account (remove via npm UI —
  provenance replaces 2FA for automated publishing).

**"Run failed at `plan` with preflight errors."**
→ `shared/scripts/release/preflight.py` reports which check failed.
  Usually stale CHANGELOG (no `[Unreleased]` populated) or version
  files out of sync (run `just rel-sync`).

**"The workflow keeps skipping."**
→ Check for stale tag on origin: `git ls-remote --tags origin
  "v$(cat VERSION)"`. If the tag exists but the publish never happened
  (because a previous run died after tag-release succeeded but before
  publish — shouldn't happen given the gate, but possible), you'll
  need to delete the tag: `git push --delete origin v<VERSION>` AFTER
  confirming with the user, and then re-run.

## Things I've gotten wrong before (do not repeat)

- Claimed a release shipped because the workflow showed green, without
  checking PyPI. It hadn't. PyPI latest was 3 versions behind master.
- Pushed `release:` commits directly to master instead of a topic
  branch + PR. That bypassed `python · lint` and `python · typecheck`
  which then failed on a subsequent unrelated PR.
- Used `just rel-prepare` on a topic branch and wondered why the
  workflow didn't trigger.
- Ran `uv publish` locally to "just get it out" instead of fixing the
  trusted-publisher config, skipping provenance + attestations in the
  process. Do NOT do this. The `rel-publish-python` recipe has a
  deliberate 3-second delay + warning for a reason.

## Files to know

| file                                              | role                                    |
|---------------------------------------------------|-----------------------------------------|
| `VERSION`                                         | single source of truth (plain semver)   |
| `python/src/adk_fluent/_version.py`               | python consumer (auto-synced)           |
| `ts/package.json`                                 | ts consumer (auto-synced)               |
| `CHANGELOG.md`                                    | `[Unreleased]` → `[X.Y.Z]` on prepare   |
| `justfile.release`                                | `rel-*` recipes                         |
| `shared/scripts/release/__main__.py`              | `python -m shared.scripts.release` CLI  |
| `shared/scripts/release/preflight.py`             | CHECKS tuple — append new checks here   |
| `shared/scripts/release/version.py`               | version read/sync/bump                  |
| `shared/scripts/release/changelog.py`             | `[Unreleased]` promotion                |
| `.github/workflows/release.yml`                   | orchestrator (plan + fan-out + tag)     |
| `.github/workflows/_publish-python.yml`           | reusable: build + publish Python        |
| `.github/workflows/_publish-npm.yml`              | reusable: build + publish ts            |

## When in doubt

Read `.github/workflows/release.yml` header comments end-to-end — they
are accurate and kept current. Then read the matching reusable workflow.
Then run `just rel-preflight --strict` locally. Only then touch anything.
