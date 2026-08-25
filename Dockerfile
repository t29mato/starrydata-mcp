# starrydata-mcp — Hugging Face Spaces (Docker SDK) image.
#
# The dataset is ingested at BUILD time (see the `RUN starrydata-mcp ingest`
# step below), not at container start: the image ships with
# starrydata.duckdb already baked in, so the container responds to
# /health immediately on boot instead of spending 15-30 minutes ingesting
# before it can serve a single request (see docs/TECHNICAL_OVERVIEW.md §2.4
# for why a full ingest takes that long). This means the image itself needs
# rebuilding to pick up a new daily snapshot — see
# docs/deploy/huggingface-spaces.md for the refresh procedure.
#
# Follows HF Spaces' Docker SDK conventions: a non-root `user` (uid 1000),
# app on port 7860, listening on 0.0.0.0.

FROM python:3.12-slim

# astral's official distroless-style image ships just the `uv`/`uvx`
# binaries — the documented way to get uv into another base image without
# a separate install step.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

RUN useradd --create-home --uid 1000 user
USER user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy
WORKDIR /home/user/app

COPY --chown=user:user pyproject.toml uv.lock README.md ./
COPY --chown=user:user src ./src

# --no-dev: production deps only (no pytest/ruff/mypy/etc. in the image).
RUN uv sync --frozen --no-dev

# Bake in a fresh DuckDB snapshot. Needs network access at build time (HF
# Spaces' build service has it) — this is the one step that can meaningfully
# fail or go stale; see docs/deploy/huggingface-spaces.md.
RUN uv run starrydata-mcp ingest

EXPOSE 7860

# HF Spaces' Docker SDK always expects the app on 7860; $PORT is honored too
# in case this ever runs somewhere that sets it (e.g. Cloud Run).
CMD ["sh", "-c", "uv run starrydata-mcp serve --http :${PORT:-7860}"]
