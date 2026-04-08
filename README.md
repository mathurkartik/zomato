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