FROM python:3.12-slim

# No Python packages needed: the server uses the standard library only.
RUN useradd --system --uid 10001 --home-dir /app tracker \
 && mkdir -p /data && chown tracker /data

WORKDIR /app
COPY index.html *.jpg site/
COPY server/ server/

ENV SITE_DIR=/app/site \
    DATA_DIR=/data \
    PORT=8080 \
    PYTHONUNBUFFERED=1

USER tracker
VOLUME /data
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/healthz',timeout=4).status==200 else 1)"
CMD ["python3", "server/app.py"]
