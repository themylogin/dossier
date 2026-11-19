FROM python:3.15-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.13.9 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app
COPY pyproject.toml uv.lock ./

FROM base AS test
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked
COPY alembic.ini ./
COPY migrations ./migrations
COPY dossier ./dossier
COPY tests ./tests
CMD ["pytest"]

FROM base AS runtime
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev
COPY alembic.ini ./
COPY migrations ./migrations
COPY dossier ./dossier
EXPOSE 8080 8090
CMD ["uvicorn", "dossier.backend.main:app", "--host", "0.0.0.0", "--port", "8080"]
