FROM node:24.21.0-alpine3.24@sha256:ebfe2f90462722a7a4de65e91990e97fe0d401c70e0e762c5b53302f905ec1c1 AS dependencies
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

FROM dependencies AS build
ENV NEXT_TELEMETRY_DISABLED=1 DEVPULSE_CONTAINER_BUILD=1
COPY . .
RUN npm run build

# Build the same Node release against patched system OpenSSL. The upstream binary
# statically embeds OpenSSL 3.5.8, which OS package upgrades cannot replace.
FROM python:3.13.16-alpine3.24@sha256:2d9aefe2fef018a7eb2c13064c89c71929800fd2e5dccdbf52ea5da5bb8d929a AS node-runtime
RUN apk add --no-cache g++ make linux-headers openssl-dev=3.5.9-r0
ADD --checksum=sha256:a6f54defb6fd7c84f41dba13d61e78e9b4e0961712cf61f29715c05f5ced94fc https://nodejs.org/dist/v24.21.0/node-v24.21.0.tar.xz /tmp/node.tar.xz
WORKDIR /build/node
RUN tar -xJf /tmp/node.tar.xz --strip-components=1 \
    && ./configure --prefix=/opt/node --shared-openssl --without-npm \
    && make -j2 \
    && make install

FROM alpine:3.24.2@sha256:294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6 AS runtime
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 HOSTNAME=0.0.0.0 PORT=3000 DEVPULSE_CONTAINER_BUILD=1
RUN apk add --no-cache libstdc++ libssl3=3.5.9-r0 libcrypto3=3.5.9-r0 ca-certificates
COPY --from=node-runtime /opt/node/bin/node /usr/local/bin/node
COPY --from=node-runtime /build/node/LICENSE /usr/local/share/licenses/node/LICENSE
WORKDIR /app
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
USER 10001:10001
EXPOSE 3000
CMD ["node", "server.js"]
