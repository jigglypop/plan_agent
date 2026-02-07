#!/bin/sh
set -e

echo "S3에서 데이터 동기화..."
aws s3 sync s3://plan-agent-data/data/ /app/data/ --quiet --exclude "chroma/*" --exclude "memory.db"
echo "동기화 완료."

echo "벡터DB 인덱싱..."
python -m src.vectordb.store
echo "인덱싱 완료. 앱 시작."

exec python main.py all
