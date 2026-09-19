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
