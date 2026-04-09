FROM node:20-alpine

WORKDIR /app

COPY apps/web/package*.json /app/apps/web/
RUN cd /app/apps/web && npm install

COPY apps/web /app/apps/web

WORKDIR /app/apps/web