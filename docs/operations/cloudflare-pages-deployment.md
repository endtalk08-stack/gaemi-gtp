# Cloudflare Pages 운영 배포 절차

## 고정 대상

- Repository: `endtalk08-stack/gaemi-gtp`
- Source branch: `main`
- Pages project: `gaemigtp-main`
- Production URL: https://gaemigtp-main.pages.dev
- Static output: `frontend/`
- Pages Functions: repository-root `functions/`
- Existing R2 binding: `DATA_R2` → `gaemigtp-news-data`

Cloudflare Pages project settings are already configured for output directory `frontend`, production branch `main`, and the existing R2 binding. The workflow must not create another Pages project or replace these settings.

## Only supported deployment route

`GitHub branch → Pull Request → single PR preview deployment → merge to main → single production deployment`

Both preview and production use the same workflow:
`.github/workflows/gaemigtp-main-pages-news-production.yml`

- Pull Request: deploy the exact PR merge commit to a Pages preview branch named `pr-<number>`.
- Before merge: validate all local HTML/CSS/JS references, build the Functions bundle, compare every deployed static asset byte-for-byte, and smoke-test existing Function routes and R2 reads.
- After merge: deploy the exact `main` commit to the production branch and repeat the same checks.
- A failed validation or asset/API comparison blocks the workflow from reporting success.

## Why deployment is a full snapshot

Cloudflare Pages Direct Upload deploys a complete static output directory, not an isolated changed file. That is expected Pages behavior. The workflow uploads the checked-out `frontend/` snapshot and the root `functions/` directory as Pages Functions. Unmodified files are expected to remain byte-identical to the same Git commit.

The workflow copies `frontend/` and `functions/` unchanged into an isolated temporary workspace and runs Wrangler from that workspace root. This keeps Wrangler installation files outside the repository while preserving the required sibling layout for Pages Functions.

## Change discipline

- Make related file changes on one feature branch and commit them together once.
- Do not issue separate production commits for HTML, JS, CSS, or version query strings.
- Never merge the historical `ops/gaemigtp-main-pages-preview` branch into `main`; it is stale and diverged.
- Do not make dashboard-side edits to Pages output or bindings as a workaround.
