FROM docker.m.daocloud.io/library/python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Build deps for packages without pre-built wheels
# apt 国内源
RUN sed -i 's/deb.debian.org/mirrors.ustc.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc python3-dev libc-dev \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --timeout 120 --retries 5 \
    --index-url https://pypi.tuna.tsinghua.edu.cn/simple .

COPY db/ db/
COPY scripts/ scripts/
COPY web/dist/ web/dist/

RUN chmod +x scripts/*.sh

CMD ["scripts/run-api.sh"]
