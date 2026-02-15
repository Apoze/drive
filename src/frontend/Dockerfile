FROM node:22-alpine AS frontend-deps

WORKDIR /home/frontend/

COPY ./src/frontend/package.json ./package.json
COPY ./src/frontend/yarn.lock ./yarn.lock
COPY ./src/frontend/apps/drive/package.json ./apps/drive/package.json

# The dev container runs as an unprivileged user (uid 1000 by default). Because `docker compose`
# mounts `/home/frontend/node_modules` as a named volume, Docker will initially populate it from
# the image layer; ensure the directory is writable by the runtime user to avoid EACCES on `yarn install`.
RUN yarn install --frozen-lockfile \
  && chown -R node:node /home/frontend/node_modules /home/frontend/apps/drive/node_modules

COPY .dockerignore ./.dockerignore
# COPY ./src/frontend/.prettierrc.js ./.prettierrc.js
#COPY ./src/frontend/packages/eslint-config-drive ./packages/eslint-config-drive
COPY ./src/frontend/apps/drive ./apps/drive

### ---- Front-end builder image ----
FROM frontend-deps AS drive

WORKDIR /home/frontend/apps/drive

FROM frontend-deps AS drive-dev

WORKDIR /home/frontend/apps/drive

EXPOSE 3000

RUN yarn build-theme
CMD ["yarn", "dev"]

# Tilt will rebuild drive target so, we dissociate drive and drive-builder 
# to avoid rebuilding the app at every changes.
FROM drive AS drive-builder

WORKDIR /home/frontend/apps/drive

ARG API_ORIGIN
ENV NEXT_PUBLIC_API_ORIGIN=${API_ORIGIN}

RUN yarn build

# ---- Front-end image ----
FROM nginxinc/nginx-unprivileged:alpine3.22 AS frontend-production

# Upgrade system packages to install security updates
USER root
RUN apk update && \
  apk upgrade && \
  rm -rf /var/cache/apk/*

# Un-privileged user running the application
ARG DOCKER_USER
USER ${DOCKER_USER}

COPY --from=drive-builder \
    /home/frontend/apps/drive/out \
    /usr/share/nginx/html

COPY ./src/frontend/apps/drive/conf/default.conf /etc/nginx/conf.d
COPY ./docker/files/usr/local/bin/entrypoint /usr/local/bin/entrypoint

ENTRYPOINT [ "/usr/local/bin/entrypoint" ]

CMD ["nginx", "-g", "daemon off;"]
