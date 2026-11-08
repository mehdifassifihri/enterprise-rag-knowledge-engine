FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml README.md requirements.lock ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.lock \
    && pip wheel --no-cache-dir --no-deps --wheel-dir /wheels .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --system app && useradd --system --gid app app
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY alembic.ini ./
COPY migrations ./migrations
USER app
EXPOSE 8000
CMD ["uvicorn", "enterprise_knowledge_engine.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
