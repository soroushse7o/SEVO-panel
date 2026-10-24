# The MTProto proxy binary is lifted from the upstream image, which is a
# `scratch` image containing a single static binary at /mtg.
FROM nineseconds/mtg:2.2.8 AS mtg

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    MTPROXY_BIN=/usr/local/bin/mtg

WORKDIR /app

COPY --from=mtg /mtg /usr/local/bin/mtg

COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /data && /usr/local/bin/mtg --version

# 8080 serves the panel over HTTP; 443 is the MTProto proxy, which Railway
# exposes separately via TCP Proxy.
EXPOSE 8080 443

CMD ["python", "main.py"]
