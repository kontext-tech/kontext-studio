#!/bin/bash
# Build Docker image for App
# Usage: ./scripts/build-app-image.sh [--tag=<tag>] [--image=<image-name>] [--container-engine=<docker|podman>] [--prefix=<image-prefix>] [--template=<prod|local>]

# Set default values
TAG="latest"
IMAGE_NAME="kontext-app"
CONTAINER_ENGINE="podman"
IMAGE_PREFIX="ghcr.io/kontext-labs/"
NGINX_TEMPLATE="local"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
  case $1 in
    --tag=*)
      TAG="${1#*=}"
      shift
      ;;
    --image=*)
      IMAGE_NAME="${1#*=}"
      shift
      ;;
    --container-engine=*)
      CONTAINER_ENGINE="${1#*=}"
      shift
      ;;
    --prefix=*)
      IMAGE_PREFIX="${1#*=}"
      shift
      ;;
    --template=*)
      NGINX_TEMPLATE="${1#*=}"
      shift
      ;;
    *)
      echo "Unknown option: $1"
      echo "Usage: ./scripts/build-app-image.sh [--tag=<tag>] [--image=<image-name>] [--container-engine=<docker|podman>] [--prefix=<image-prefix>] [--template=<prod|local>]"
      exit 1
      ;;
  esac
done

# Determine project directory
SCRIPT_PATH=$(realpath "$0")
SCRIPT_DIR=$(dirname "$SCRIPT_PATH")
PROJECT_DIR=$(dirname "$SCRIPT_DIR")

# Extract version from the workspace package metadata
PUBLIC_KONTEXT_VERSION=$(node -p "require('${PROJECT_DIR}/package.json').version")
if [ -z "$PUBLIC_KONTEXT_VERSION" ]; then
  PUBLIC_KONTEXT_VERSION="0.0.0"
fi

echo "Using PUBLIC_KONTEXT_VERSION: $PUBLIC_KONTEXT_VERSION"

# Source environment variables for local build
if [ -f "${PROJECT_DIR}/.env.local" ]; then
  echo "Loading environment variables from .env.local"
  set -o allexport
  source "${PROJECT_DIR}/.env.local"
  set +o allexport
else
  echo "Warning: .env.local not found. Using default or environment-provided variables."
  # Set defaults if .env.local is not found, or rely on them being in the execution environment
  PUBLIC_KONTEXT_APP_URL=${PUBLIC_KONTEXT_APP_URL:-http://localhost:8002}
  PUBLIC_KONTEXT_URL=${PUBLIC_KONTEXT_URL:-http://localhost:8006}
  PUBLIC_KONTEXT_API_URL=${PUBLIC_KONTEXT_API_URL:-http://localhost:8101}
  INTERNAL_KONTEXT_API_URL=${INTERNAL_KONTEXT_API_URL:-http://kontext-api:8080}
  PUBLIC_GOOGLE_ANALYTICS_ID=${PUBLIC_GOOGLE_ANALYTICS_ID:-}
fi

# Create full image name with prefix
FULL_IMAGE_NAME="${IMAGE_PREFIX}${IMAGE_NAME}"
echo "Building $FULL_IMAGE_NAME:$TAG with $CONTAINER_ENGINE under $PROJECT_DIR/app"

# Expose the app port for local development
EXPOSE_PORTS=(8002)

# Build the Docker image
if [ "$NGINX_TEMPLATE" = "prod" ]; then
  BUILD_TARGET="production"
  echo "Building for production (exposing port 80)"
else
  BUILD_TARGET="local"
  echo "Building for local development (exposing ports 8002)"
fi

$CONTAINER_ENGINE build \
  --target $BUILD_TARGET \
  --build-arg NODE_ENV=production \
  --build-arg NGINX_TEMPLATE=${NGINX_TEMPLATE} \
  --build-arg PUBLIC_KONTEXT_APP_URL=${PUBLIC_KONTEXT_APP_URL} \
  --build-arg PUBLIC_KONTEXT_URL=${PUBLIC_KONTEXT_URL} \
  --build-arg PUBLIC_KONTEXT_API_URL=${PUBLIC_KONTEXT_API_URL} \
  --build-arg INTERNAL_KONTEXT_API_URL=${INTERNAL_KONTEXT_API_URL} \
  --build-arg PUBLIC_KONTEXT_VERSION=${PUBLIC_KONTEXT_VERSION} \
  --build-arg PUBLIC_GOOGLE_ANALYTICS_ID=${PUBLIC_GOOGLE_ANALYTICS_ID} \
  -t $FULL_IMAGE_NAME:$TAG \
  -f ${PROJECT_DIR}/app/Dockerfile \
  ${PROJECT_DIR}

# Report success
# Print exposed ports for clarity
for port in "${EXPOSE_PORTS[@]}"; do
  echo "Exposing port: $port"
done

echo "Successfully built $FULL_IMAGE_NAME:$TAG"
