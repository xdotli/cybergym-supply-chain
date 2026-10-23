# SPDX-License-Identifier: BSD-3-Clause

# OpenEnv environment image for cybergym_supply_chain.
# Build: DOCKER_DEFAULT_PLATFORM=linux/amd64 openenv build -t ghcr.io/<you>/cybergym-supply-chain:v1

ARG BASE_IMAGE=ghcr.io/huggingface/openenv-base:latest
FROM ${BASE_IMAGE} AS builder

WORKDIR /app

RUN apt-get update && \
    apt-get install -y --no-install-recommends git && \
    rm -rf /var/lib/apt/lists/*

COPY . /app/env
WORKDIR /app/env

RUN if ! command -v uv >/dev/null 2>&1; then \
        curl -LsSf https://astral.sh/uv/install.sh | sh && \
        mv /root/.local/bin/uv /usr/local/bin/uv && \
        mv /root/.local/bin/uvx /usr/local/bin/uvx; \
    fi

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-install-project --no-editable

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --no-editable || true

RUN mv /app/env/.venv /app/.venv

FROM ${BASE_IMAGE}

WORKDIR /app

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/env /app/env
RUN ln -s /app/.venv /app/env/.venv

RUN apt-get update && apt-get install -y --no-install-recommends git openssl && rm -rf /var/lib/apt/lists/*

# Generate the task artifacts and answer hashes into the image.
RUN cd /app/env/server && python3 gen_tasks.py && \
    (cd tasks/deleted-secret-history && sh build_history.sh) && \
    python3 tasks/chain-of-trust/build_certs.py

ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app/env:$PYTHONPATH"
ENV SUPPLY_CHAIN_TASKS="/app/env/server/tasks"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["sh", "-c", "cd /app/env && uvicorn server.app:app --host 0.0.0.0 --port 8000"]
