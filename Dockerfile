FROM python:3.12-slim

ARG HTTP_PROXY
ARG HTTPS_PROXY
ARG NO_PROXY
ARG PIP_INDEX_URL
ARG PIP_EXTRA_INDEX_URL
ARG PLAYWRIGHT_DOWNLOAD_HOST
ARG PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST
ARG PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=180000

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    MODELSCOPE_STATE_DIR=/data \
    PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT=${PLAYWRIGHT_DOWNLOAD_CONNECTION_TIMEOUT} \
    TZ=Asia/Shanghai

WORKDIR /app

COPY requirements.txt ./

RUN if [ -n "$HTTP_PROXY" ]; then export HTTP_PROXY="$HTTP_PROXY" http_proxy="$HTTP_PROXY"; fi \
    && if [ -n "$HTTPS_PROXY" ]; then export HTTPS_PROXY="$HTTPS_PROXY" https_proxy="$HTTPS_PROXY"; fi \
    && if [ -n "$NO_PROXY" ]; then export NO_PROXY="$NO_PROXY" no_proxy="$NO_PROXY"; fi \
    && if [ -n "$PIP_INDEX_URL" ]; then export PIP_INDEX_URL="$PIP_INDEX_URL"; fi \
    && if [ -n "$PIP_EXTRA_INDEX_URL" ]; then export PIP_EXTRA_INDEX_URL="$PIP_EXTRA_INDEX_URL"; fi \
    && if [ -n "$PLAYWRIGHT_DOWNLOAD_HOST" ]; then export PLAYWRIGHT_DOWNLOAD_HOST="$PLAYWRIGHT_DOWNLOAD_HOST"; fi \
    && if [ -n "$PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST" ]; then export PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST="$PLAYWRIGHT_CHROMIUM_DOWNLOAD_HOST"; fi \
    && python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY login_and_save.py ./
COPY modelscope_keep_alive.py ./
COPY modelscope_keep_alive.template.json ./
COPY README.md ./

RUN mkdir -p /data

CMD ["python", "modelscope_keep_alive.py", "--browser-channel", "chromium"]
