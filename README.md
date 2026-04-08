# zomato

## Run on Streamlit (local)

From project root:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

## Deploy on Streamlit Cloud

1. Push this repo to GitHub.
2. In Streamlit Cloud, create a new app from this repo.
3. Set main file path to:
   - `streamlit_app.py`
4. (Optional, for LLM ranking) add secret/env var:
   - `GROQ_API_KEY=<your_key>`

If `GROQ_API_KEY` is not set, app still works using deterministic fallback recommendations.

## Deploy FastAPI on Render

This repo includes `render.yaml` for one-click API deployment.

### Steps

1. In Render, create a **Blueprint** from this GitHub repo.
2. Render will detect `render.yaml` and create service `zomato-fastapi`.
3. Add secret env var in Render:
   - `GROQ_API_KEY=<your_key>`
4. Deploy and wait for build to complete.

Expected API base URL:

- `https://<your-render-service>.onrender.com`

Quick checks:

- `GET /health`
- `GET /api/v1/filters`

Then use this URL in frontend host (Vercel):

- `NEXT_PUBLIC_API_URL=https://<your-render-service>.onrender.com`