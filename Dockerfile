FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    MODELSCOPE_STATE_DIR=/data \
    TZ=Asia/Shanghai

WORKDIR /app

COPY requirements.txt ./

RUN python -m pip install --upgrade pip \
    && python -m pip install -r requirements.txt \
    && python -m playwright install --with-deps chromium

COPY login_and_save.py ./
COPY modelscope_keep_alive.py ./
COPY modelscope_keep_alive.template.json ./
COPY README.md ./

RUN mkdir -p /data

CMD ["python", "modelscope_keep_alive.py", "--browser-channel", "chromium"]
