# Chiron backend (FastAPI + LangGraph) for Cloud Run.
# Built remotely by Cloud Build: `gcloud run deploy --source .` (see deploy/cloudrun.sh).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

# Only what the server needs: code, clinical cases and the prebuilt RAG index (.chroma).
COPY agents/ agents/
COPY api/ api/
COPY llm/ llm/
COPY rag/ rag/
COPY store/ store/
COPY cases/ cases/
COPY .chroma/ .chroma/

# Cloud Run injects PORT. Secrets (Gemini keys, DATABASE_URL, CHIRON_BACKEND_SECRET, LangSmith)
# come from Secret Manager as environment variables, never from a .env in the image.
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}
