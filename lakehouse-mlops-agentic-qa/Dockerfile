FROM python:3.11-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md ./
COPY src/ src/
RUN pip wheel --no-cache-dir --wheel-dir /wheels ".[aws]"

FROM python:3.11-slim

WORKDIR /app

COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir --no-index --find-links=/wheels lmq[aws] \
    && rm -rf /wheels

COPY configs/ configs/
COPY data/raw/ data/raw/
COPY tests/golden/ tests/golden/

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

ENTRYPOINT ["lmq"]
CMD ["serve", "--host", "0.0.0.0"]
