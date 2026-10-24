# --- Aether tunnel client (pinned release, sha256-verified) -------------------
FROM debian:bookworm-slim AS aether
ARG TARGETARCH
ARG AETHER_VERSION=v1.5.0
RUN apt-get update && \
    apt-get install -y --no-install-recommends curl ca-certificates tar gzip && \
    rm -rf /var/lib/apt/lists/*
RUN set -eux; \
    case "$TARGETARCH" in \
      amd64) A=x86_64 ;; \
      arm64) A=aarch64 ;; \
      *) echo "unsupported arch: $TARGETARCH" >&2; exit 1 ;; \
    esac; \
    base="https://github.com/CluvexStudio/Aether/releases/download/${AETHER_VERSION}"; \
    f="aether-linux-${A}-musl.tar.gz"; \
    curl -fsSL "$base/$f" -o "/tmp/$f"; \
    curl -fsSL "$base/$f.sha256" -o "/tmp/$f.sha256"; \
    exp="$(cut -d' ' -f1 "/tmp/$f.sha256" | tr 'A-Z' 'a-z')"; \
    echo "$exp  /tmp/$f" | sha256sum -c -; \
    mkdir -p /opt/aether; \
    tar -xzf "/tmp/$f" -C /opt/aether; \
    chmod +x /opt/aether/aether

# The MTProto proxy binary is lifted from the upstream image, which is a
# `scratch` image containing a single static binary at /mtg.
FROM nineseconds/mtg:2.2.8 AS mtg

FROM python:3.11-slim

ARG AETHER_VERSION=v1.5.0
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MTPROXY_BIN=/usr/local/bin/mtg \
    AETHER_BIN=/usr/local/bin/aether \
    AETHER_VERSION=${AETHER_VERSION}

WORKDIR /app

COPY --from=mtg /mtg /usr/local/bin/mtg
COPY --from=aether /opt/aether/aether /usr/local/bin/aether

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data && /usr/local/bin/mtg --version && /usr/local/bin/aether --version || true

# 8080 serves the panel over HTTP; 443 is the MTProto proxy, which Railway
# exposes separately via TCP Proxy. Aether's SOCKS5 listens on 127.0.0.1 only.
EXPOSE 8080 443

# /health is public and returns HTTP 503 when the database is unreachable.
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,sys,urllib.request as u; sys.exit(0 if u.urlopen('http://127.0.0.1:%s/health' % os.environ.get('PORT','8080'), timeout=4).status == 200 else 1)"

CMD ["python", "main.py"]
