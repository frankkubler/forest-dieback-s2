FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.32 /uv /uvx /bin/
RUN apt-get update && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

# Dépendances d'abord (couche mise en cache), uv.lock pris s'il existe
COPY pyproject.toml README.md .python-version uv.lock* ./
COPY src ./src
RUN uv sync --no-dev --extra gee

COPY configs ./configs
COPY scripts ./scripts
COPY Makefile ./

ENV PATH="/app/.venv/bin:$PATH"
CMD ["make", "demo", "RUN="]
