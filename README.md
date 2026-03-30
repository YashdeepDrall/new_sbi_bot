# SBI Chatbot

This project is scoped for SBI fraud investigation workflows and now uses a Gemini-based RAG path instead of the old local heavy-model setup.

- Backend: FastAPI APIs for login, fraud analysis, SOP retrieval, and document download
- Frontend: Streamlit chat interface for SBI investigators
- Knowledge base: `banks/sbi/SBI_SOP.pdf`
- Database: currently replaced with in-memory runtime state
- RAG: Gemini embeddings + Gemini answer generation through API calls
- Vector storage: document chunk embeddings are cached locally on disk and reused for unchanged PDFs

What has already been removed:

- Docker files and Docker-based deployment flow
- `build/` artifacts
- `dist/` artifacts
- MongoDB/GridFS runtime dependency
- FAISS, sentence-transformers, NumPy, and other heavy local model dependencies

## Environment

Set these values in `.env` or your deployment environment:

- `GEMINI_API_KEY=your_api_key`
- `GEMINI_GENERATION_MODEL=gemini-3.1-flash-lite-preview`
- `GEMINI_EMBEDDING_MODEL=gemini-embedding-2-preview`

Optional tuning:

- `GEMINI_EMBEDDING_DIMENSION=768`
- `RAG_TOP_K=4`
- `RAG_MIN_SIMILARITY=0.2`

The app now writes its reusable local vector cache to `local_cache/sbi_vectors.json`.

Inference from current official Gemini docs plus the live API check in this workspace: the accepted generation model here is `gemini-3.1-flash-lite-preview`, and the embedding model request `gemini-embedding-2-preview` is also being accepted. The code still includes fallbacks to officially documented close models when needed.

## Local run

1. Install packages from `requirements.txt`
2. Set `GEMINI_API_KEY`
3. Start the FastAPI backend
4. Start the Streamlit app

Default local login:

- User ID: `sbi001`
- Password: `0000`

The next improvement area is refining the prompt/output format and polishing the Gemini RAG response quality now that the heavy local dependency path is gone.

## Render deploy

This repo is prepared for a two-service Render deployment:

- Backend web service: FastAPI API
- Frontend web service: Streamlit UI

Files added for Render:

- `render.yaml`
- `.python-version`
- `requirements-backend.txt`
- `requirements-frontend.txt`
- `scripts/precompute_vectors.py`

Important free-tier note:

- Render web services use an ephemeral filesystem by default.
- Runtime-written files are not durable across deploys, restarts, or instance replacement.
- To avoid re-embedding the SBI SOP on every cold start, the backend build now precomputes `local_cache/sbi_vectors.json` during the build step.
- On a new deploy, the cache is rebuilt once during build.
- On normal restarts of that same deploy, the baked-in cache is reused.

How to deploy on Render:

1. Push this repo to GitHub.
2. In Render, create a new Blueprint from the repo.
3. Render will detect `render.yaml` and create:
   - `sbi-fraud-api`
   - `sbi-fraud-ui`
4. When prompted, set the backend secret `GEMINI_API_KEY`.
5. Deploy both services.
6. Open the frontend URL and log in with:
   - User ID: `sbi001`
   - Password: `0000`

How the services connect:

- The frontend reads `API_BASE_URL`.
- In `render.yaml`, that variable is populated from the backend service's `RENDER_EXTERNAL_URL`.
- This uses the backend's public Render URL, which is the right fit for two free web services.
