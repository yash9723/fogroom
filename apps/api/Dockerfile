FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.lock ./
RUN pip install --upgrade pip && pip install -r requirements.lock

COPY . .
RUN pip install --no-deps . && useradd --create-home fogroom && chown -R fogroom /app
USER fogroom

EXPOSE 8000
CMD ["sh", "./docker-entrypoint.sh"]
