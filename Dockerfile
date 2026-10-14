FROM python:3.11-slim

WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends make \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --extra-index-url https://download.pytorch.org/whl/cpu \
    -e ".[gee,onnx]"

COPY configs ./configs
COPY scripts ./scripts
COPY Makefile ./

CMD ["make", "demo"]
