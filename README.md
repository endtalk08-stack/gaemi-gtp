# gaemiGTP

Refactored structure preserving the existing UI and API behavior.

## Run locally

```bash
pip install -r requirements.txt
python app.py
```

## Render

Keep the existing Start Command:

```bash
gunicorn app:app
```

The frontend is served by the same Flask process, so the browser uses same-origin `/analyze` requests.
