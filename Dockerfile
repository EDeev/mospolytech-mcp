FROM python:3.14-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
RUN python -c "import tomllib; [print(d) for d in tomllib.load(open('pyproject.toml', 'rb'))['project']['dependencies']]" \
    | pip install -r /dev/stdin

COPY README.md alembic.ini ./
COPY src ./src
COPY alembic ./alembic
RUN pip install --no-deps .

RUN useradd --create-home --uid 1000 mcp
USER mcp

EXPOSE 8000

CMD ["sh", "-c", "alembic upgrade head && exec python -m mospolytech_mcp.server --http --host 0.0.0.0 --port 8000"]
