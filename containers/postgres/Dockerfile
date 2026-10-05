FROM postgres:18-alpine3.24@sha256:77f585114c32fbca283dc835b0596f4e52b51b4c6662d7810b2f4084f60a1873
# Replace the bundled Go-based gosu with Alpine's equivalent privilege-drop helper.
# Keep the official entrypoint, initialization, signal handling, and database tools.
RUN apk add --no-cache su-exec=0.3-r0 nghttp2-libs=1.70.0-r0 libssl3=3.5.9-r0 libcrypto3=3.5.9-r0 \
    && sed -i 's/exec gosu postgres/exec su-exec postgres/' /usr/local/bin/docker-entrypoint.sh \
    && rm /usr/local/bin/gosu
