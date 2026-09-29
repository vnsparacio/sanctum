FROM node:26-bookworm@sha256:347d9d5391493c2fc3f0d161b75a9cab64a9805064b1b01b099f8ee97f98ed47

WORKDIR /opt/sanctum-qwen
COPY package.json package-lock.json ./
RUN npm ci --omit=dev \
 && npm cache clean --force \
 && groupadd --gid 65532 sanctum-qwen \
 && useradd --uid 65532 --gid 65532 --create-home --home-dir /home/qwen --shell /usr/sbin/nologin sanctum-qwen \
 && mkdir -p /workspace /poc /evidence \
 && chown 65532:65532 /workspace /poc /evidence

ENV PATH="/opt/sanctum-qwen/node_modules/.bin:${PATH}"
USER 65532:65532
WORKDIR /workspace
