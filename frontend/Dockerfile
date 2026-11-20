# ==========================================
# Multi-stage Dockerfile para SkillMatch Frontend
# ==========================================

# Etapa 1: Build de la aplicación Vite
FROM node:20-alpine AS builder

WORKDIR /app

# Instalar dependencias
COPY package.json package-lock.json ./
RUN npm ci

# Copiar código fuente
COPY . .

# Compilar bundle de producción
RUN npm run build

# ==========================================
# Etapa 2: Servidor Web Nginx
# ==========================================
FROM nginx:alpine AS runner

# Copiar configuración personalizada de Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar assets estáticos compilados desde el builder
COPY --from=builder /app/dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
