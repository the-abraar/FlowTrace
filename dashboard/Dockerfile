# Static build served by nginx. Vite reads VITE_* at build time, so the read key is a build arg, not a runtime env.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG VITE_READ_API_KEY=""
ENV VITE_READ_API_KEY=$VITE_READ_API_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /app/dist /usr/share/nginx/html
# single-page app on port 3000 (the compose mapping). REST calls are relative (/api/v1/...), so nginx proxies them to the
# compose `backend` service, as the Vite dev proxy does; /ws is proxied too (upgrade headers).
RUN printf 'server {\n  listen 3000;\n  root /usr/share/nginx/html;\n  location /api/ { proxy_pass http://backend:8000; }\n  location /ws { proxy_pass http://backend:8000; proxy_http_version 1.1; proxy_set_header Upgrade $http_upgrade; proxy_set_header Connection \"upgrade\"; }\n  location / { try_files $uri /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 3000
