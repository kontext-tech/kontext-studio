# Build stage for the labs application
FROM docker.io/library/node:lts-alpine3.21 AS labs_build

# Install pinned pnpm and bash
RUN apk add --no-cache bash && npm install -g pnpm@10.24.0

WORKDIR /app

# Copy labs package manifests and lockfile
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./

# Copy scripts needed for shared package builds (SDK clients are committed source)
COPY scripts/ ./scripts/
# tools/ holds validate-workspace-graph.mjs, which build-shared-packages.sh runs
COPY tools/ ./tools/

# Copy the source code for the app and its dependencies
COPY ts/ ./ts/
COPY app/ ./app/

# Install all dependencies for the app and its workspace dependencies
RUN pnpm install --frozen-lockfile

# Build shared dependencies first to ensure their outputs are available
RUN bash ./scripts/build-shared-packages.sh

# Set build args as environment variables for Vite
ARG PUBLIC_KONTEXT_VERSION
ARG PUBLIC_KONTEXT_URL
ARG PUBLIC_KONTEXT_APP_URL
ARG PUBLIC_KONTEXT_API_URL
ARG PUBLIC_GOOGLE_ANALYTICS_ID
ENV PUBLIC_KONTEXT_VERSION=${PUBLIC_KONTEXT_VERSION}
ENV PUBLIC_KONTEXT_URL=${PUBLIC_KONTEXT_URL}
ENV PUBLIC_KONTEXT_APP_URL=${PUBLIC_KONTEXT_APP_URL}
ENV PUBLIC_KONTEXT_API_URL=${PUBLIC_KONTEXT_API_URL}
ENV PUBLIC_GOOGLE_ANALYTICS_ID=${PUBLIC_GOOGLE_ANALYTICS_ID}

# Set NODE_OPTIONS to increase memory limit for the build process
ENV NODE_OPTIONS=--max-old-space-size=4096

# Build the app application
# PNPM will automatically build any workspace dependencies first.
RUN pnpm --filter @kontext-tech/app build:prod

# Base nginx stage
FROM docker.io/library/nginx:alpine AS nginx_base

# Install envsubst utility for template processing
RUN apk add --no-cache bash gettext

# Create a directory for logs and link them to stdout/stderr for container log capture
RUN mkdir -p /var/log/nginx && \
    ln -sf /dev/stdout /var/log/nginx/labs.access.log && \
    ln -sf /dev/stderr /var/log/nginx/labs.error.log

# Argument to specify which nginx template to use: 'prod' or 'local' (default)
ARG NGINX_TEMPLATE=local

# Copy the nginx configuration templates
COPY app/default.conf.template /etc/nginx/templates/default.conf.template.prod
COPY app/default.conf.local.template /etc/nginx/templates/default.conf.template.local

# Create symbolic link to the selected template
RUN ln -sf /etc/nginx/templates/default.conf.template.${NGINX_TEMPLATE} /etc/nginx/templates/default.conf.template

# Copy built labs application files to /usr/share/nginx/html/labs
RUN mkdir -p /usr/share/nginx/html/labs
COPY --from=labs_build /app/app/dist /usr/share/nginx/html/labs

# Copy startup script
COPY app/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Add VERSION and API URL build args
ARG PUBLIC_KONTEXT_VERSION
ARG PUBLIC_KONTEXT_URL
ARG PUBLIC_KONTEXT_APP_URL
ARG PUBLIC_KONTEXT_API_URL
ARG PUBLIC_KONTEXT_DATA_API_URL
ARG PUBLIC_GOOGLE_ANALYTICS_ID

# Environment variables with defaults
ENV NGINX_PORT=80 \
    NGINX_HOST=localhost \
    PUBLIC_KONTEXT_VERSION=${PUBLIC_KONTEXT_VERSION} \
    PUBLIC_KONTEXT_URL=${PUBLIC_KONTEXT_URL} \
    PUBLIC_KONTEXT_APP_URL=${PUBLIC_KONTEXT_APP_URL} \
    PUBLIC_KONTEXT_API_URL=${PUBLIC_KONTEXT_API_URL} \
    PUBLIC_KONTEXT_DATA_API_URL=${PUBLIC_KONTEXT_DATA_API_URL} \
    PUBLIC_GOOGLE_ANALYTICS_ID=${PUBLIC_GOOGLE_ANALYTICS_ID}

# Production stage
FROM nginx_base AS production
EXPOSE 80
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

# Local development stage
FROM nginx_base AS local
EXPOSE 80
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]

# Default to local development stage
FROM local AS final
