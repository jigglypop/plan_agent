#!/bin/sh
set -e

echo "S3에서 데이터 동기화..."
if ! aws s3 sync s3://plan-agent-data/data/ /app/data/ --quiet --exclude "chroma/*" --exclude "memory.db"; then
    echo "S3 동기화 실패. 로컬 데이터로 계속 진행합니다."
fi
echo "동기화 완료."

echo "벡터DB 인덱싱..."
if ! python -m src.vectordb.store; then
    echo "벡터DB 인덱싱 실패. 런타임에서 재시도합니다."
fi
echo "인덱싱 완료. 앱 시작."

exec python main.py all
