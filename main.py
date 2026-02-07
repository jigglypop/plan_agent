"""
Plan Agent - 메인 실행 파일
FastAPI 서버 + Discord 봇 동시 실행
"""
import os
import sys
import threading
from dotenv import load_dotenv

load_dotenv()


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
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "api":
        print("FastAPI 서버만 실행합니다.")
        run_api()

    elif mode == "discord":
        print("Discord 봇만 실행합니다.")
        run_discord()

    elif mode == "all":
        print("FastAPI 서버 + Discord 봇을 실행합니다.")
        # API 서버를 별도 스레드에서 실행
        api_thread = threading.Thread(target=run_api, daemon=True)
        api_thread.start()
        # Discord 봇은 메인 스레드에서 (이벤트 루프 필요)
        try:
            run_discord()
        except Exception as e:
            print(f"Discord 봇 실패: {e}")
            print("API 서버만 유지합니다.")
            api_thread.join()

    elif mode == "status":
        from src.agent import Agent
        agent = Agent()
        status = agent.is_ready()
        print("=== Plan Agent 상태 ===")
        print(f"OpenAI: {'연결' if status['openai'] else '미연결'}")
        print(f"게시글: {status['posts_count']}건")
        print(f"VectorDB: {status['vectordb']}")

    else:
        print("사용법: python main.py [api|discord|all|status]")


if __name__ == "__main__":
    main()
