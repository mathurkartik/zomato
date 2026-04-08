## Frontend (Next.js)

### Local development

1. Copy env file:
   ```bash
   cp .env.example .env.local
   ```
2. Set backend API URL:
   - `NEXT_PUBLIC_API_URL=http://localhost:8000`
3. Run:
   ```bash
   npm install
   npm run dev
   ```

### Production deployment (Vercel recommended)

Set this environment variable in your frontend host:

- `NEXT_PUBLIC_API_URL=<your_backend_base_url>`

Example:

- `NEXT_PUBLIC_API_URL=https://zomato-oai.streamlit.app`

### Important

The frontend expects these API endpoints on the backend URL:

- `GET /health`
- `GET /api/v1/filters`
- `GET /api/v1/filters/cuisines`
- `GET /api/v1/filters/cuisines/summary`
- `POST /api/v1/filters/counts`
- `POST /api/v1/recommend`

If your backend URL does not expose these routes, frontend API calls will fail.
