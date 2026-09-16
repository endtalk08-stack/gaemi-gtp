# Render/Gunicorn entrypoint. Keep Start Command as: gunicorn app:app
from backend.app import app, application

__all__ = ["app", "application"]
