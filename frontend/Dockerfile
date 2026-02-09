FROM node:22-alpine AS build

WORKDIR /app

COPY package.json pnpm-lock.yaml* package-lock.json* ./
RUN corepack enable 2>/dev/null; \
    if [ -f pnpm-lock.yaml ]; then pnpm install --frozen-lockfile; \
    elif [ -f package-lock.json ]; then npm ci; \
    else npm install; fi

COPY . .
# Skip vue-tsc type check in Docker (done locally); run vite build directly
RUN if [ -f pnpm-lock.yaml ]; then pnpm exec vite build; else npx vite build; fi

# --- Nginx ---
FROM nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
