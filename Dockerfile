# syntax=docker/dockerfile:1
ARG BASE_IMAGE=pitsdevops.azurecr.io/pits-linux-base

############################################################
# Stage 1 — build: PIT base image + Node 22 + Vite production build
############################################################
FROM ${BASE_IMAGE} AS build

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl gnupg; \
    mkdir -p /etc/apt/keyrings; \
    curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
        | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg; \
    echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
        > /etc/apt/sources.list.d/nodesource.list; \
    apt-get update; \
    apt-get install -y --no-install-recommends nodejs; \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# ----------------------------------------------------------
# Install dependencies
# ----------------------------------------------------------
COPY package.json package-lock.json ./
RUN npm ci

# ----------------------------------------------------------
# Copy application source
# ----------------------------------------------------------
COPY . .

# ==========================================================
# VITE APPLICATION VARIABLES
# ==========================================================

ARG VITE_API_BASE_URL
ARG VITE_ENTRA_CLIENT_ID
ARG VITE_ENTRA_TENANT_ID
ARG VITE_ENTRA_REDIRECT_URI
ARG VITE_DEFAULT_TENANT_SLUG
# Short source revision shown in the admin sidebar footer (app-shell spec).
ARG VITE_BUILD_SHA

# ==========================================================
# FIREBASE VARIABLES
# Used by Firebase Cloud Messaging (FCM)
# ==========================================================

ARG VITE_FIREBASE_API_KEY
ARG VITE_FIREBASE_AUTH_DOMAIN
ARG VITE_FIREBASE_PROJECT_ID
ARG VITE_FIREBASE_STORAGE_BUCKET
ARG VITE_FIREBASE_MESSAGING_SENDER_ID
ARG VITE_FIREBASE_APP_ID
ARG VITE_FIREBASE_MEASUREMENT_ID
ARG VITE_FIREBASE_VAPID_KEY

# ----------------------------------------------------------
# Make variables available during Vite build
# ----------------------------------------------------------
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_ENTRA_CLIENT_ID=$VITE_ENTRA_CLIENT_ID \
    VITE_ENTRA_TENANT_ID=$VITE_ENTRA_TENANT_ID \
    VITE_ENTRA_REDIRECT_URI=$VITE_ENTRA_REDIRECT_URI \
    VITE_DEFAULT_TENANT_SLUG=$VITE_DEFAULT_TENANT_SLUG \
    VITE_BUILD_SHA=$VITE_BUILD_SHA \
    VITE_FIREBASE_API_KEY=$VITE_FIREBASE_API_KEY \
    VITE_FIREBASE_AUTH_DOMAIN=$VITE_FIREBASE_AUTH_DOMAIN \
    VITE_FIREBASE_PROJECT_ID=$VITE_FIREBASE_PROJECT_ID \
    VITE_FIREBASE_STORAGE_BUCKET=$VITE_FIREBASE_STORAGE_BUCKET \
    VITE_FIREBASE_MESSAGING_SENDER_ID=$VITE_FIREBASE_MESSAGING_SENDER_ID \
    VITE_FIREBASE_APP_ID=$VITE_FIREBASE_APP_ID \
    VITE_FIREBASE_MEASUREMENT_ID=$VITE_FIREBASE_MEASUREMENT_ID \
    VITE_FIREBASE_VAPID_KEY=$VITE_FIREBASE_VAPID_KEY

# ----------------------------------------------------------
# Build Vite production bundle
# ----------------------------------------------------------
RUN npm run build


############################################################
# Stage 2 — runtime: PIT base image + nginx
############################################################
FROM ${BASE_IMAGE} AS runtime

ENV DEBIAN_FRONTEND=noninteractive

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends nginx curl libcap2-bin; \
    rm -rf /var/lib/apt/lists/*; \
    ln -sf /dev/stdout /var/log/nginx/access.log; \
    ln -sf /dev/stderr /var/log/nginx/error.log; \
    rm -f /etc/nginx/sites-enabled/default; \
    setcap 'cap_net_bind_service=+ep' /usr/sbin/nginx; \
    sed -i \
        -e 's/^user www-data;/#user www-data;/' \
        -e 's#^pid /run/nginx.pid;#pid /tmp/nginx.pid;#' \
        /etc/nginx/nginx.conf

# ----------------------------------------------------------
# Copy Vite production build
# ----------------------------------------------------------
COPY --from=build /app/dist /usr/share/nginx/html

# ----------------------------------------------------------
# Nginx configuration
# ----------------------------------------------------------
COPY nginx.conf /etc/nginx/conf.d/default.conf

# ----------------------------------------------------------
# Non-root application user
# ----------------------------------------------------------
RUN useradd --system --create-home --uid 1001 appuser \
    && chown -R appuser:appuser \
        /usr/share/nginx/html \
        /var/lib/nginx \
        /var/log/nginx

USER appuser

EXPOSE 80

# ----------------------------------------------------------
# Container health check
# ----------------------------------------------------------
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -fsS http://127.0.0.1/health || exit 1

CMD ["/usr/sbin/nginx", "-g", "daemon off;"]