# ==============================================================================
# RepoPilot Frontend Dockerfile — Multi-Stage Build & NGINX Production Serve
# ==============================================================================

# ---- Stage 1: Build static assets ----
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package manifests and install dependencies
COPY package.json package-lock.json /app/
RUN npm ci

# Copy source code and build production assets
COPY . /app/
ARG VITE_API_BASE_URL=http://localhost:8000
ENV VITE_API_BASE_URL=${VITE_API_BASE_URL}

RUN npm run build

# ---- Stage 2: Serve with NGINX ----
FROM nginx:alpine

# Copy built static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP port
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
