# Multi-stage: la imagen de build tiene Node y el toolchain; la salida son
# solo ficheros estáticos que sirve Caddy. Node no viaja a producción.

FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install
COPY . .
RUN npm run build

# El resultado (dist/) lo monta el proxy Caddy vía volumen en docker-compose,
# así que esta etapa final solo expone el artefacto compilado.
FROM scratch AS export
COPY --from=build /app/dist /dist
