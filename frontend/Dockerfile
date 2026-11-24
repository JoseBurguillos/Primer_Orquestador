# ---------- Fase 1: compilar Angular ----------
FROM node:22 AS compilar
WORKDIR /app

# Primero las dependencias (en caché si no cambian)
COPY package.json package-lock.json ./
RUN npm install --legacy-peer-deps

# Después el código, y compilamos
COPY . .
RUN npx ng build

# ---------- Fase 2: servir la web con Nginx ----------
FROM nginx:alpine

# Copiamos solo el resultado de la fase 1
COPY --from=compilar /app/dist/frontend/browser /usr/share/nginx/html

EXPOSE 80