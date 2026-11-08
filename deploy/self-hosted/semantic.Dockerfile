FROM node@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d
WORKDIR /app
COPY service/ ./
COPY public/library.json ./library.json
COPY public/openapi.json ./openapi.json
COPY scripts/semantic-report.mjs ./semantic-report.mjs
COPY scripts/evaluation-contracts/ ./evaluation-contracts/
RUN mkdir -p /state && chown node:node /state
ENV EVALUATION_SNAPSHOT_PATH=/app/library.json
USER node
CMD ["node", "server.mjs"]
