# Louvre's container image, which the Helm chart (charts/louvre) runs. `make image` builds it locally; the Image
# workflow builds and pushes it to GHCR from main and from each v* tag.
#
# The version is built from git tags (D004), and the build context carries no .git, so it comes in as VERSION:
# `make image` and the workflow compute it with uv-dynamic-versioning's own CLI.

# The web UI, built with the Node its package.json asks for.
FROM node:22-slim AS ui
WORKDIR /src/ui
COPY ui/package.json ui/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY ui/ ./
RUN npm run build

# louvre's wheel, with the built UI bundled in (hatch_build.py finds no npm here and takes ui/dist as it is), and a
# virtual environment holding it and the dependencies uv.lock pins.
FROM python:3.12-slim AS build
RUN pip install --no-cache-dir uv==0.11.32
WORKDIR /src
ARG VERSION=0.0.0
ENV UV_DYNAMIC_VERSIONING_BYPASS=${VERSION} \
    UV_PYTHON_DOWNLOADS=never \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy
COPY pyproject.toml uv.lock README.md LICENSE hatch_build.py ./
COPY src src
COPY docs/ui-explorations docs/ui-explorations
COPY ui/package.json ui/package.json
COPY --from=ui /src/ui/dist ui/dist
RUN uv export --frozen --no-dev --no-emit-project --no-hashes -o requirements.txt \
    && uv build --wheel --out-dir wheels \
    && uv venv /app \
    && uv pip install --python /app/bin/python --no-cache -r requirements.txt \
    && uv pip install --python /app/bin/python --no-cache --no-deps wheels/*.whl

FROM python:3.12-slim
COPY --from=build /app /app
ENV PATH=/app/bin:${PATH} \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# A user with no home and no shell login; the chart runs it with a read-only root filesystem.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin louvre
USER 10001:10001
EXPOSE 8000
ENTRYPOINT ["louvre"]
CMD ["serve", "--host", "0.0.0.0", "--port", "8000"]
