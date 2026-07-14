FROM python:3.12-slim AS backend-deps

WORKDIR /backend
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/ .


FROM node:20-bookworm-slim AS frontend-build

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
ENV BACKEND_INTERNAL_URL=http://127.0.0.1:8000
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build \
    && if [ -f .next/standalone/server.js ]; then \
         mv .next/standalone /tmp/standalone; \
       elif [ -f .next/standalone/frontend/server.js ]; then \
         mv .next/standalone/frontend /tmp/standalone; \
       else \
         echo "standalone server.js not found" && find .next -name server.js && exit 1; \
       fi


FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=node:20-bookworm-slim /usr/local/bin/node /usr/local/bin/node

WORKDIR /app

COPY --from=backend-deps /usr/local/lib/python3.12/site-packages /usr/local/lib/python3.12/site-packages
COPY --from=backend-deps /usr/local/bin /usr/local/bin
COPY --from=backend-deps /backend /app/backend

COPY --from=frontend-build /tmp/standalone /app/frontend
COPY --from=frontend-build /frontend/.next/static /app/frontend/.next/static
COPY --from=frontend-build /frontend/public /app/frontend/public

COPY scripts/start.sh /app/start.sh
RUN chmod +x /app/start.sh \
    && mkdir -p /app/data \
    && node --version \
    && test -f /app/frontend/server.js

ENV DJANGO_DEBUG=False \
    DATABASE_PATH=/app/data/db.sqlite3 \
    BACKEND_INTERNAL_URL=http://127.0.0.1:8000 \
    ALLOWED_HOSTS=* \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

EXPOSE 3000

CMD ["/app/start.sh"]
