FROM node:20-slim

ENV NODE_ENV=production

RUN npm install -g opencode-ai@latest && \
    npm cache clean --force

EXPOSE 5097

CMD ["opencode", "web", "--port", "5097", "--hostname", "0.0.0.0"]
