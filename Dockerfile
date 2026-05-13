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
RUN groupadd --system --gid 1000 ting && \
    useradd --system --uid 1000 --gid ting --home /app --no-create-home ting
COPY --from=builder --chown=ting:ting /install /app/lib
COPY --chown=ting:ting src/ /app/src/
COPY --chown=ting:ting migrations/ /app/migrations/
COPY --chown=ting:ting alembic.ini /app/
COPY --chown=ting:ting seeds/ /app/seeds/
USER ting
EXPOSE 8000
CMD ["uvicorn", "ting.app:app", "--host", "0.0.0.0", "--port", "8000"]
