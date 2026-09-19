FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

RUN addgroup --system app && adduser --system --ingroup app app
COPY pyproject.toml README.md ./
COPY src ./src
COPY evals ./evals
COPY tests ./tests
COPY scripts ./scripts
RUN pip install --no-cache-dir ".[api]" && chown -R app:app /app

USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["uvicorn", "agent_lab.api:app", "--host", "0.0.0.0", "--port", "8000"]
