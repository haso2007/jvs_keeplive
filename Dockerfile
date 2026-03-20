FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir playwright \
    && playwright install chromium \
    && playwright install-deps

COPY jvs_keep_alive.py .
COPY jvs_keep_alive.template.json .

CMD ["python", "jvs_keep_alive.py"]
