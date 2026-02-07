# Stage 1: 프론트엔드 빌드
FROM node:20-slim AS frontend

WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: 백엔드 + 프론트엔드 정적 파일
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl unzip \
    && curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o /tmp/awscli.zip \
    && unzip -q /tmp/awscli.zip -d /tmp \
    && /tmp/aws/install \
    && rm -rf /tmp/aws /tmp/awscli.zip \
    && apt-get purge -y curl unzip \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY main.py .
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# 프론트엔드 빌드 결과물 복사
COPY --from=frontend /build/dist frontend/dist

RUN mkdir -p data

EXPOSE 8000

ENTRYPOINT ["./entrypoint.sh"]
