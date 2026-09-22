# gaemi-gtp

## Refactored structure
- Render start command: `gunicorn app:app`
- Frontend: `frontend/`
- Backend wrapper: `backend/app.py`
- Analysis/data engine: `backend/services/engine.py`
- Health check: `/health`
- Analysis API: `/analyze?stock=삼성전자`
- The frontend calls the API with same-origin `window.location.origin`.


## Deployment
- GitHub Pages serves the frontend from `frontend/index.html` via the root redirect.
- Render runs `gunicorn app:app` and serves the same frontend plus `/analyze` and `/health`.
- The browser calls the Render API at `https://gaemi-gtp.onrender.com`.

## 2026-09-22 panel layout stabilization
The right panel is fixed as the right sibling column inside `gaemiWorkspace`. The extra panel left/right dock button was removed. Only the divider resizer changes panel width, up to 1200px where the viewport allows. The home hero now gives the panel its own right-side space instead of hiding/overlaying the main workspace.
