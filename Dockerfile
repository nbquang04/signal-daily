FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY daily_news/ daily_news/
COPY web/ web/
COPY data/ data/
COPY output/ output/
COPY config.json README.md ./

RUN mkdir -p /app/data/archives /app/output

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3)"

CMD ["python", "-m", "daily_news.server", "--host", "0.0.0.0", "--port", "8000", "--refresh-hours", "0"]
