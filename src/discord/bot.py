"""
Discord 봇
기획위원회 AI 에이전트 + 정기 작업 (주간 리포트, 리마인더)
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional

import discord
from discord import Intents
from discord.ext import tasks

from src.agent import Agent
from src.data import get_post_stats, load_posts


logger = logging.getLogger(__name__)


intents = Intents.default()
intents.message_content = True

client = discord.Client(intents=intents)
agent: Optional[Agent] = None

ALLOWED_CHANNELS = [
    ch.strip()
    for ch in os.getenv("DISCORD_CHANNELS", "").split(",")
    if ch.strip()
]


# ========== 이벤트 핸들러 ==========

@client.event
async def on_ready():
    global agent
    agent = Agent()
    status = agent.is_ready()
    logger.info("Discord 봇 시작: %s", client.user)
    logger.info("  OpenAI: %s", "연결" if status.get("openai") else "미연결")
    logger.info("  Notion: %s", "연결" if status.get("notion") else "미연결")
    logger.info("  게시글: %s건 로드", status.get("posts_count"))
    logger.info("  VectorDB: %s", status.get("vectordb"))

    # 정기 작업 시작
    if not weekly_report.is_running():
        weekly_report.start()


@client.event
async def on_message(message: discord.Message):
    if message.author == client.user:
        return

    query, should_respond = _parse_message(message)
    if not should_respond or not query:
        return

    session_id = _get_session_id(message)

    # 리셋 명령
    if query.strip() in ("리셋", "초기화", "/reset"):
        agent.reset(session_id)
        await message.reply("대화가 초기화되었습니다.")
        return

    # 에이전트 응답
    async with message.channel.typing():
        response = await asyncio.to_thread(agent.chat, query, session_id)

    await _send_response(message, response)


# ========== 정기 작업 ==========

@tasks.loop(hours=168)  # 매주
async def weekly_report():
    """주간 게시판 활동 리포트 발송"""
    if not ALLOWED_CHANNELS:
        return

    posts = load_posts()
    stats = get_post_stats(posts)
    now = datetime.now()

    report = (
        f"[주간 리포트] {now.strftime('%Y-%m-%d')}\n"
        f"총 게시글: {stats['total_posts']}건\n"
        f"총 첨부파일: {stats['total_files']}개\n"
        f"기간: {stats['year_range']}"
    )

    for ch_id in ALLOWED_CHANNELS:
        channel = client.get_channel(int(ch_id))
        if channel:
            await channel.send(report)


@weekly_report.before_loop
async def before_weekly():
    await client.wait_until_ready()


# ========== 유틸리티 ==========

def _parse_message(message: discord.Message) -> tuple:
    """메시지 파싱: (query, should_respond)"""
    query = message.content

    # DM
    if isinstance(message.channel, discord.DMChannel):
        return query, True

    # 멘션
    if client.user and client.user.mentioned_in(message):
        query = query.replace(f"<@{client.user.id}>", "").strip()
        return query, True

    # 지정 채널
    if ALLOWED_CHANNELS and str(message.channel.id) in ALLOWED_CHANNELS:
        return query, True

    return query, False


def _get_session_id(message: discord.Message) -> str:
    """메시지에서 세션 ID 추출"""
    if isinstance(message.channel, discord.DMChannel):
        return f"dm-{message.author.id}"
    return f"ch-{message.channel.id}"


async def _send_response(message: discord.Message, response: str):
    """Discord 2000자 제한 처리하여 응답"""
    if len(response) <= 2000:
        await message.reply(response)
        return

    chunks = _split_message(response, 2000)
    for i, chunk in enumerate(chunks):
        if i == 0:
            await message.reply(chunk)
        else:
            await message.channel.send(chunk)


def _split_message(text: str, limit: int) -> list:
    """줄바꿈 기준 분할"""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""
    for line in text.split("\n"):
        if len(current) + len(line) + 1 > limit:
            if current:
                chunks.append(current)
            current = line[:limit]
        else:
            current = f"{current}\n{line}" if current else line

    if current:
        chunks.append(current)

    return chunks


def run_bot():
    """Discord 봇 실행"""
    from src import configure_logging
    configure_logging()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN 환경변수가 설정되지 않았습니다.")
        return
    client.run(token)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_bot()
