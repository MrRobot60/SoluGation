# Interface de production : compilation (Node), puis service par Caddy (HTTPS automatique, proxy vers l'API).
# Contexte de construction : racine du dépôt (la rubrique Aide embarque docs/).
FROM node:24-alpine AS construction
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
COPY docs/ /app/docs/
RUN npm run build

FROM caddy:2.10-alpine
COPY deploiement/Caddyfile /etc/caddy/Caddyfile
COPY --from=construction /app/frontend/dist /srv
