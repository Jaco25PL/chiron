# Chiron backend (FastAPI + LangGraph). Runs on Hugging Face Spaces (Docker SDK, free CPU tier;
# see deploy/hf_space.py) and on any container host (Cloud Run, Render…).
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Spaces run containers as uid 1000; give that user the app dir (Chroma writes its SQLite files).
RUN useradd -m -u 1000 user
USER user
ENV HOME=/home/user PATH=/home/user/.local/bin:$PATH
WORKDIR /home/user/app

COPY --chown=user requirements.txt .
RUN pip install --user -r requirements.txt

# Only what the server needs: code, clinical cases and the prebuilt RAG index (.chroma).
COPY --chown=user agents/ agents/
COPY --chown=user api/ api/
COPY --chown=user llm/ llm/
COPY --chown=user rag/ rag/
COPY --chown=user store/ store/
COPY --chown=user cases/ cases/
COPY --chown=user .chroma/ .chroma/

# PORT: Spaces use the app_port from the Space README (7860); Cloud Run injects its own.
# Secrets (Gemini keys, DATABASE_URL, CHIRON_BACKEND_SECRET, LangSmith) come from the host's
# secret store as environment variables, never from a .env in the image.
EXPOSE 7860
CMD exec uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-7860}
