FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --index-url https://pypi.tuna.tsinghua.edu.cn/simple . 2>&1

COPY scripts/ scripts/
COPY web/dist/ web/dist/

RUN chmod +x scripts/*.sh

CMD ["scripts/run-api.sh"]
