FROM python:3.11-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY evals ./evals
COPY tests ./tests
COPY scripts ./scripts
RUN pip install --no-cache-dir .

ENV PYTHONUNBUFFERED=1
CMD ["python", "-m", "production_rag.cli", "evaluate", "--json"]
