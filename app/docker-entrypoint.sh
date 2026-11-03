#!/bin/bash
# Docker entrypoint script for the frontend container
# This script processes environment variables and starts nginx

set -e

# Generate nginx config from template
echo "Configuring nginx..."

# Print some debug information
echo "Environment variables:"
echo "NGINX_HOST: $NGINX_HOST"
echo "NGINX_PORT: $NGINX_PORT"
echo "INTERNAL_KONTEXT_API_URL: $INTERNAL_KONTEXT_API_URL"
echo "INTERNAL_KONTEXT_API_HOST: $INTERNAL_KONTEXT_API_HOST"
echo "PUBLIC_KONTEXT_API_URL: $PUBLIC_KONTEXT_API_URL"
echo "PUBLIC_KONTEXT_URL: $PUBLIC_KONTEXT_URL"
echo "PUBLIC_KONTEXT_APP_URL: $PUBLIC_KONTEXT_APP_URL"
echo "PUBLIC_KONTEXT_VERSION: $PUBLIC_KONTEXT_VERSION"

# Print Nginx version for debugging
nginx -v

echo "Note: Environment configuration is already injected during build process"

# Export variables for envsubst (with fallback defaults to prevent nginx errors)
export ENV_NGINX_HOST=${NGINX_HOST:-localhost}
export ENV_NGINX_PORT=${NGINX_PORT:-80}
export ENV_PUBLIC_KONTEXT_API_URL=${PUBLIC_KONTEXT_API_URL:-http://localhost:8000}
export ENV_PUBLIC_KONTEXT_APP_URL=${PUBLIC_KONTEXT_APP_URL:-http://localhost:8002}
export ENV_PUBLIC_KONTEXT_URL=${PUBLIC_KONTEXT_URL:-http://localhost:8002}
export ENV_PUBLIC_KONTEXT_DATA_API_URL=${PUBLIC_KONTEXT_DATA_API_URL:-http://localhost:8000}
export ENV_IS_DEVELOPMENT=${IS_DEVELOPMENT:-false}

# Ensure SSR/static app sees all PUBLIC_ env vars
export PUBLIC_KONTEXT_VERSION="${PUBLIC_KONTEXT_VERSION}"
export PUBLIC_KONTEXT_URL="${PUBLIC_KONTEXT_URL}"
export PUBLIC_KONTEXT_APP_URL="${PUBLIC_KONTEXT_APP_URL}"
export PUBLIC_KONTEXT_API_URL="${PUBLIC_KONTEXT_API_URL}"
export PUBLIC_KONTEXT_DATA_API_URL="${PUBLIC_KONTEXT_DATA_API_URL}"
export PUBLIC_GOOGLE_ANALYTICS_ID="${PUBLIC_GOOGLE_ANALYTICS_ID}"
export IS_DEVELOPMENT="${ENV_IS_DEVELOPMENT}"

# Inject environment variables into index.html at runtime
# This allows the same image to be used in different environments
echo "Injecting runtime environment variables into index.html..."
INDEX_HTML="/usr/share/nginx/html/labs/index.html"
if [ -f "$INDEX_HTML" ]; then
  # Create a single-line JS object with the environment variables
  ENV_JSON="{\"PUBLIC_KONTEXT_API_URL\": \"$ENV_PUBLIC_KONTEXT_API_URL\", \"PUBLIC_KONTEXT_DATA_API_URL\": \"$ENV_PUBLIC_KONTEXT_DATA_API_URL\", \"PUBLIC_KONTEXT_URL\": \"$ENV_PUBLIC_KONTEXT_URL\", \"PUBLIC_KONTEXT_APP_URL\": \"$ENV_PUBLIC_KONTEXT_APP_URL\", \"IS_DEVELOPMENT\": $ENV_IS_DEVELOPMENT, \"VERSION\": \"$PUBLIC_KONTEXT_VERSION\"}"

  # Replace the window.ENV block in index.html
  # We use a simplified approach: replace the entire script block if we can find it
  sed -i "s|window.ENV = {.*};|window.ENV = $ENV_JSON;|g" "$INDEX_HTML" || echo "Warning: Could not inject runtime ENV into index.html"
fi

# Validate critical environment variables
echo "Validating environment variables..."
echo "ENV_PUBLIC_KONTEXT_API_URL: $ENV_PUBLIC_KONTEXT_API_URL"

# Initialize production hostnames to a dummy value that won't match
export ENV_NGINX_HOST_PROD_WEBSITE="_"
export ENV_NGINX_HOST_PROD_APP="_"
export ENV_API_DOMAIN_NAME="_"

# Check PUBLIC_KONTEXT_URL for production website hostname
if [[ -n "$PUBLIC_KONTEXT_URL" && ! "$PUBLIC_KONTEXT_URL" =~ "localhost" ]]; then
  export ENV_NGINX_HOST_PROD_WEBSITE=$(echo "$PUBLIC_KONTEXT_URL" | sed -e 's%^https\?://%%' -e 's%[:/].*$%%')
fi

# Check PUBLIC_KONTEXT_APP_URL for production platform app hostname
if [[ -n "$PUBLIC_KONTEXT_APP_URL" && ! "$PUBLIC_KONTEXT_APP_URL" =~ "localhost" ]]; then
  export ENV_NGINX_HOST_PROD_APP=$(echo "$PUBLIC_KONTEXT_APP_URL" | sed -e 's%^https\?://%%' -e 's%[:/].*$%%')
fi

# Check PUBLIC_KONTEXT_API_URL for API domain hostname
if [[ -n "$PUBLIC_KONTEXT_API_URL" && ! "$PUBLIC_KONTEXT_API_URL" =~ "localhost" ]]; then
  export ENV_API_DOMAIN_NAME=$(echo "$PUBLIC_KONTEXT_API_URL" | sed -e 's%^https\?://%%' -e 's%[:/].*$%%')
fi

echo "Derived ENV_NGINX_HOST_PROD_WEBSITE: $ENV_NGINX_HOST_PROD_WEBSITE"
echo "Derived ENV_NGINX_HOST_PROD_APP: $ENV_NGINX_HOST_PROD_APP"
echo "Derived ENV_API_DOMAIN_NAME: $ENV_API_DOMAIN_NAME"

# For development environment (localhost), add a server_port variable that nginx can use to preserve the port in redirects
if [[ "$PUBLIC_KONTEXT_APP_URL" =~ "localhost" ]]; then
  export ENV_SERVER_PORT=$(echo "$PUBLIC_KONTEXT_APP_URL" | sed -n 's/.*:\([0-9][0-9]*\).*/\1/p')
  if [ -z "$ENV_SERVER_PORT" ]; then export ENV_SERVER_PORT="80"; fi
  echo "Derived ENV_SERVER_PORT: $ENV_SERVER_PORT"
else
  export ENV_SERVER_PORT="80"
fi

# Process Nginx template files
# Ensure all necessary ENV_ variables are listed for substitution
envsubst '${ENV_NGINX_HOST} ${ENV_NGINX_PORT} ${ENV_NGINX_HOST_PROD_WEBSITE} ${ENV_NGINX_HOST_PROD_APP} ${ENV_API_DOMAIN_NAME} ${ENV_SERVER_PORT} ${ENV_PUBLIC_KONTEXT_API_URL} ${ENV_PUBLIC_KONTEXT_APP_URL} ${ENV_PUBLIC_KONTEXT_URL}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

# Execute the CMD (e.g., nginx -g 'daemon off;')
exec "$@"
