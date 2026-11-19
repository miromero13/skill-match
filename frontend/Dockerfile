# syntax=docker/dockerfile:1.7
#
# SkillMatch frontend image (build context: ./frontend).
#
# Targets:
#   dev      Vite dev server on 0.0.0.0:5173 (hot reload; used by compose.override.yaml).
#   runtime  Default (last stage): static SPA on nginx-unprivileged :8080 that also reverse-proxies
#            /api/ and /ws/ to http://backend:8000 (see nginx/default.conf).
#
# Every VITE_* value is baked into the JavaScript bundle at build time: changing one requires a rebuild.
# Never pass secrets as build args; these values are public by design.

ARG NODE_IMAGE=node:22-bookworm-slim
ARG NGINX_IMAGE=nginxinc/nginx-unprivileged:1.29-alpine

# ------------------------------------------------------------------------------
# deps: reproducible install from package-lock.json.
# `postinstall` runs scripts/install-vision-assets.mjs --wasm-only (offline copy of the MediaPipe wasm into
# public/mediapipe/wasm), so scripts/ must be present before `npm ci`.
# ------------------------------------------------------------------------------
FROM ${NODE_IMAGE} AS deps

ENV CI=true \
    NPM_CONFIG_AUDIT=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_UPDATE_NOTIFIER=false

WORKDIR /app
RUN chown node:node /app
USER node

COPY --chown=node:node package.json package-lock.json ./
COPY --chown=node:node scripts ./scripts
RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000,sharing=locked \
    npm ci

# ------------------------------------------------------------------------------
# dev: Vite dev server (compose.override.yaml bind-mounts the source over /app).
# `predev` installs the MediaPipe model with --soft (a download failure is only a warning).
# ------------------------------------------------------------------------------
FROM deps AS dev

ENV NODE_ENV=development
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# ------------------------------------------------------------------------------
# build: type-check + production bundle. `prebuild` downloads and SHA-256 verifies the MediaPipe model with
# --soft (the backend weights are outside this build context).
# ------------------------------------------------------------------------------
FROM deps AS build

# Required: absolute http(s) URL ending in /api, e.g. https://skillmatch.example.com/api
# (same origin as the nginx runtime, which proxies /api/ and /ws/ to the backend).
ARG VITE_API_URL
ARG VITE_APP_ENV=production
ARG VITE_GOOGLE_CLIENT_ID=""
ARG VITE_GOOGLE_IOS_CLIENT_ID=""
ARG VITE_BROWSER_SUPERVISION_TRIAL=""

RUN case "${VITE_API_URL}" in \
      http://?*/api|https://?*/api) ;; \
      *) echo "ERROR: build arg VITE_API_URL must be an absolute http(s) URL ending in /api (e.g. --build-arg VITE_API_URL=https://skillmatch.example.com/api); got: '${VITE_API_URL}'" >&2; \
         exit 1 ;; \
    esac

# Build-stage only: these never reach the runtime image (separate FROM below).
ENV VITE_API_URL=${VITE_API_URL} \
    VITE_APP_ENV=${VITE_APP_ENV} \
    VITE_GOOGLE_CLIENT_ID=${VITE_GOOGLE_CLIENT_ID} \
    VITE_GOOGLE_IOS_CLIENT_ID=${VITE_GOOGLE_IOS_CLIENT_ID} \
    VITE_BROWSER_SUPERVISION_TRIAL=${VITE_BROWSER_SUPERVISION_TRIAL}

COPY --chown=node:node . .
# Equivalent to `npm run build` (prebuild + tsc -b + vite build) but type-checks only the shipped code
# (tsconfig.app.json + tsconfig.node.json). The test project (tsconfig.test.json, src/test) is not part of the
# bundle; its type errors must be caught by `npm run typecheck` in CI, not block the runtime image.
RUN npm run prebuild \
    && npx --no-install tsc -b tsconfig.app.json tsconfig.node.json \
    && npx --no-install vite build

# ------------------------------------------------------------------------------
# runtime (default target): unprivileged nginx (uid 101) serving dist/ on :8080.
# ------------------------------------------------------------------------------
FROM ${NGINX_IMAGE} AS runtime

COPY nginx/default.conf /etc/nginx/conf.d/default.conf
COPY nginx/security-headers.conf /etc/nginx/snippets/security-headers.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz >/dev/null || exit 1
