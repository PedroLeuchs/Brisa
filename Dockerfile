# syntax=docker/dockerfile:1
FROM node:22-bookworm-slim AS frontend
WORKDIR /source
RUN corepack enable
ENV NODE_USE_ENV_PROXY=1
COPY frontend /source/frontend
COPY static /source/static
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/proxy_ca; fi && \
    corepack prepare pnpm@11.25.0 --activate && \
    cd frontend && pnpm install --frozen-lockfile && pnpm build

FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN --mount=type=secret,id=proxy_ca \
    if [ -f /run/secrets/proxy_ca ]; then export PIP_CERT=/run/secrets/proxy_ca; fi && \
    pip install --no-cache-dir -r requirements.txt
COPY . /app
COPY --from=frontend /source/frontend/dist /app/frontend/dist
ENV TUYA_TRANSPORT=cloud COOKIE_SECURE=true TUYA_CLOUD_REGION=us
EXPOSE 8080
CMD ["sh", "-c", "export ALLOWED_HOSTS=${ALLOWED_HOSTS:-${RENDER_EXTERNAL_HOSTNAME:-localhost,127.0.0.1}}; exec uvicorn app:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
