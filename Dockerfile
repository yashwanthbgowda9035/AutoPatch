# Safe public-preview image. No Docker CLI/socket or host-code execution is installed.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AUTOPATCH_PUBLIC_DEMO=1 \
    AUTOPATCH_ALLOWED_HOSTS=localhost,127.0.0.1

WORKDIR /app
COPY backend/requirements.txt /tmp/autopatch-requirements.txt
RUN python -m pip install --no-cache-dir -r /tmp/autopatch-requirements.txt \
    && useradd --create-home --uid 10001 --shell /usr/sbin/nologin autopatch

COPY --chown=10001:10001 backend /app/backend
COPY --chown=10001:10001 frontend /app/frontend
COPY --chown=10001:10001 examples /app/examples
USER 10001
EXPOSE 8015

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8015') + '/health', timeout=3)" || exit 1

CMD ["sh", "-c", "exec python -m uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8015}"]
