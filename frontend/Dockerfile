# ── develop ──────────────────────────────────────────────────
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund --fetch-retries=3 --fetch-retry-mintimeout=10000 --fetch-retry-maxtimeout=60000

FROM deps AS develop
WORKDIR /app
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host"]

# ── build ────────────────────────────────────────────────────
FROM deps AS build
WORKDIR /app
COPY . .
ARG VITE_API_BASE=/api
ENV VITE_API_BASE=${VITE_API_BASE}
RUN npm run build

# ── prod ─────────────────────────────────────────────────────
FROM nginx:1.30.6-alpine AS prod
RUN apk upgrade --no-cache \
    && apk add --no-cache 'zlib>=1.4-r0' \
    && apk del curl nginx-module-xslt nginx-module-njs nginx-module-image-filter nginx-module-geoip nginx-module-acme
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY nginx-seguridad.inc /etc/nginx/seguridad.inc
EXPOSE 80
HEALTHCHECK --interval=15s --timeout=5s --retries=5 \
    CMD wget -qO- http://127.0.0.1/api/health || exit 1
CMD ["nginx", "-g", "daemon off;"]
