FROM node@sha256:5ec23b7c622b00547753bc6ffd78085dd868a68aeb41c8e0a1418f033e13d96d
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund
COPY convex/ ./convex/
COPY local/self-hosted/seed.json ./seed.json
COPY deploy/self-hosted/deploy.sh ./deploy.sh
COPY deploy/self-hosted/operator.mjs ./operator.mjs
ENTRYPOINT ["sh", "/app/deploy.sh"]
