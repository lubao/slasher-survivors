# GitFlow Workflow

This repository follows the GitFlow branching model. Apply these conventions for all branching, committing, and merging work.

## Long-Lived Branches

- **`main`** — Production-ready code only. Every commit is a releasable state. Never commit directly; only merge from `release/*` or `hotfix/*` (or `develop` for simple projects).
- **`develop`** — Integration branch for the next release. Feature branches merge here.

## Supporting Branches

| Branch type | Branches from | Merges into | Naming |
|-------------|---------------|-------------|--------|
| Feature | `develop` | `develop` | `feature/<short-description>` |
| Release | `develop` | `main` and `develop` | `release/<version>` |
| Hotfix | `main` | `main` and `develop` | `hotfix/<short-description>` |

## Rules

- **Never commit directly to `main` or `develop`.** Always work on a supporting branch and merge.
- **Never push directly to `main`** unless explicitly directed by the user.
- Use **descriptive, kebab-case** branch names (e.g., `feature/backend-api`, `feature/game-core`).
- Keep feature branches **focused and short-lived**; rebase or merge `develop` in regularly to reduce drift.
- Use **`--no-ff`** when merging feature branches into `develop` so the history preserves the branch grouping.
- Delete feature branches after they are merged.

## Commit Messages

Follow Conventional Commits:

```
<type>(<scope>): <subject>
```

- **Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`, `build`
- **Scope** is optional but encouraged (e.g., `feat(backend):`, `feat(game):`).
- Subject is imperative, lower-case, no trailing period.

Examples (from this repo's history):
- `feat(backend): FastAPI scores/leaderboard/achievements on DynamoDB`
- `feat(game): horde-survival core simulation and rendering`
- `chore: expand .gitignore for CDK, coverage and logs`

## Releases

1. Branch `release/<version>` from `develop`.
2. Finalize version bumps, changelog, and last-minute fixes on the release branch.
3. Merge into `main`, tag with the version (`vX.Y.Z`), then merge back into `develop`.

## Hotfixes

1. Branch `hotfix/<description>` from `main`.
2. Fix, then merge into both `main` (tagged) and `develop`.
