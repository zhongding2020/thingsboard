FROM node:20-slim

ENV NODE_ENV=production

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
      python3 python3-pip python3-venv \
      build-essential libpython3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && npm install -g opencode-ai@latest \
    && npm cache clean --force

RUN mkdir -p /root/.config/opencode

COPY config/opencode.jsonc /root/.config/opencode/
COPY config/AGENTS.md /root/.opencode/

EXPOSE 5097

CMD ["opencode", "web", "--port", "5097", "--hostname", "0.0.0.0"]
