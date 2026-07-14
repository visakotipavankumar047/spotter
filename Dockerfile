FROM python:3.12-slim AS backend-deps

WORKDIR /backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .

FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
ENV BACKEND_INTERNAL_URL=http://127.0.0.1:8000
RUN npm run build

FROM python:3.12-slim

COPY --from=node:20-alpine /usr/local/bin/node /usr/local/bin/node
COPY --from=node:20-alpine /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -sf /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -sf /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

WORKDIR /app

COPY --from=backend-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin
COPY --from=backend-deps /backend /app/backend
COPY --from=frontend-build /frontend /app/frontend

COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh && mkdir -p /app/data

ENV DJANGO_DEBUG=False \
    DATABASE_PATH=/app/data/db.sqlite3 \
    BACKEND_INTERNAL_URL=http://127.0.0.1:8000 \
    ALLOWED_HOSTS=* \
    PORT=3000 \
    HOSTNAME=0.0.0.0

EXPOSE 3000

CMD ["/app/start.sh"]
