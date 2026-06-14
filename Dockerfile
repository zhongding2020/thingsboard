FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml ./
COPY src/ src/
RUN pip install --no-cache-dir .

COPY scripts/ scripts/
COPY web/dist/ web/dist/

RUN chmod +x scripts/*.sh

CMD ["scripts/run-api.sh"]