"""
Plan Agent - 메인 실행 파일
FastAPI 서버 + Discord 봇 동시 실행
"""
import os
import sys
import threading
import logging
from dotenv import load_dotenv

load_dotenv()

from src import configure_logging

logger = logging.getLogger(__name__)


def run_api():
    """FastAPI 서버 실행"""
    import uvicorn
    port = int(os.getenv("API_PORT", "8000"))
    uvicorn.run("src.api.server:app", host="0.0.0.0", port=port)


def run_discord():
    """Discord 봇 실행"""
    from src.discord import run_bot
    run_bot()


def main():
    configure_logging()
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "api":
        logger.info("FastAPI 서버만 실행합니다.")
        run_api()

    elif mode == "discord":
        logger.info("Discord 봇만 실행합니다.")
        run_discord()

    elif mode == "all":
        logger.info("FastAPI 서버 + Discord 봇을 실행합니다.")
        # API 서버를 별도 스레드에서 실행
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        # Discord 봇은 메인 스레드에서 (이벤트 루프 필요)
        try:
            run_discord()
        except Exception as e:
            logger.exception("Discord 봇 실패: %s", e)
            logger.warning("API 서버만 유지합니다.")
            api_thread.join()

    elif mode == "status":
        from src.agent import Agent
        agent = Agent()
        status = agent.is_ready()
        logger.info("=== Plan Agent 상태 ===")
        logger.info("OpenAI: %s", "연결" if status.get("openai") else "미연결")
        logger.info("게시글: %s건", status.get("posts_count"))
        logger.info("VectorDB: %s", status.get("vectordb"))

    else:
        logger.info("사용법: python main.py [api|discord|all|status]")


if __name__ == "__main__":
    main()
