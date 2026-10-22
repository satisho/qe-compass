# Production image: builds the front end, then serves everything from one Python process.
FROM node:22-alpine AS web
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    QEC_HOST=0.0.0.0 QEC_PORT=8000 QEC_DATA_DIR=/data QEC_FRONTEND_DIR=/app/frontend/dist
WORKDIR /app/backend
COPY backend/requirements.txt deploy/requirements-postgres.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-postgres.txt
COPY backend/ ./
COPY --from=web /web/dist /app/frontend/dist
RUN useradd --system --uid 10001 qec && mkdir -p /data && chown qec /data
USER qec
VOLUME ["/data"]
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health')"
CMD ["python", "-m", "app"]
