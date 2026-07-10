# Multi-stage: the build image has Node and the toolchain; the output is
# just static files served by Caddy. Node never ships to production.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# The result (dist/) is mounted by the Caddy proxy via a volume in docker-compose,
# so this final stage only exposes the compiled artifact.
FROM scratch AS export
COPY --from=build /app/dist /dist
