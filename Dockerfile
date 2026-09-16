FROM python:3.12-slim

# Install curl only to fetch uv's installer, then remove it in the same layer so it
# doesn't linger in the final image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -LsSf https://astral.sh/uv/install.sh | sh \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Dependencies first, in their own layer: this layer is cached and skipped on
# rebuilds unless pyproject.toml/uv.lock actually change, so an app-code-only
# change doesn't re-resolve or re-download the whole dependency set (including
# the CPU-only PyTorch wheel) every time.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Bake the embedding and reranker model weights into the image at build time,
# never downloaded at runtime. Render's free tier filesystem is not guaranteed to
# persist across cold starts/redeploys, and re-downloading from Hugging Face Hub
# on every cold start would be slow and risk hitting unauthenticated rate limits —
# the same warning already observed throughout local development, worse under a
# free tier's frequent cold starts. Model names kept in sync by hand with
# app/config.py's embedding_model_name and app/retrieval/reranker.py's
# RERANKER_MODEL_NAME — if either changes, this line needs updating too.
RUN uv run python -c "\
from sentence_transformers import SentenceTransformer, CrossEncoder; \
SentenceTransformer('BAAI/bge-small-en-v1.5'); \
CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# App code last: changes here are the most frequent, so they invalidate only this
# layer, not the dependency-install or model-download layers above it.
COPY app ./app
COPY alembic.ini ./

# Render sets $PORT dynamically; 8000 is the local-dev fallback if run elsewhere
# (e.g. `docker run` without Render's environment). Migrations run before the
# server starts, not as a separate manual step, so the deployed schema can never
# drift ahead of what the deployed code expects.
CMD uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
