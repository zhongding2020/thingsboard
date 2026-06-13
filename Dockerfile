FROM python:3.11-slim

ENV PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir --index-url https://pypi.tuna.tsinghua.edu.cn/simple .

COPY scripts/ scripts/
COPY web/dist/ web/dist/

RUN chmod +x scripts/*.sh

CMD ["scripts/run-api.sh"]