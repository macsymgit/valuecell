# Build context must be ./frontend (see compose.yaml at the repo root).
FROM oven/bun:1.3.3 AS build
WORKDIR /app
COPY package.json bun.lock ./
RUN bun install --frozen-lockfile
COPY . .
# Same-origin API path; nginx proxies /api to the backend container, so the
# bundle doesn't depend on any host port.
ENV VITE_API_BASE_URL=/api/v1
RUN bun run build

FROM nginx:1.27-alpine
COPY --from=build /app/build/client /usr/share/nginx/html
# nginx.conf is mounted by compose (docker/nginx.conf).
EXPOSE 80
