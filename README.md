# gaemi-gtp

## Refactored structure
- Render start command: `gunicorn app:app`
- Frontend: `frontend/`
- Backend wrapper: `backend/app.py`
- Analysis/data engine: `backend/services/engine.py`
- Health check: `/health`
- Analysis API: `/analyze?stock=삼성전자`
- The frontend calls the API with same-origin `window.location.origin`.
