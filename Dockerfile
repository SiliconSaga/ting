FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml ./
COPY src/ ./src/
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir --target=/install .

FROM python:3.12-slim
WORKDIR /app
ENV PYTHONPATH=/app/lib \
    PYTHONUNBUFFERED=1 \
    PATH=/app/lib/bin:$PATH
COPY --from=builder /install /app/lib
COPY src/ /app/src/
COPY migrations/ /app/migrations/
COPY alembic.ini /app/
COPY seeds/ /app/seeds/
EXPOSE 8000
CMD ["uvicorn", "ting.app:app", "--host", "0.0.0.0", "--port", "8000"]
