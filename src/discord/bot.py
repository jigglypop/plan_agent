"""
Discord 봇 (py-cord 기반)
기획위원회 AI 에이전트 + 정기 작업 (주간 리포트) + STT 회의록
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
from src.data_loader import get_post_stats
from src.stt.recorder import VoiceRecorder
from src.stt.transcriber import transcribe_audio, generate_minutes


logger = logging.getLogger(__name__)


intents = Intents.default()
intents.message_content = True

bot = discord.Bot(intents=intents)
agent: Optional[Agent] = None
_recorder = VoiceRecorder()

ALLOWED_CHANNELS = [
    ch.strip()
    for ch in os.getenv("DISCORD_CHANNELS", "").split(",")
    if ch.strip()
]


# ========== 이벤트 핸들러 ==========

@bot.event
async def on_ready():
    global agent
    agent = Agent()
    status = agent.is_ready()
    logger.info("Discord 봇 시작: %s", bot.user)
    logger.info("  OpenAI: %s", "연결" if status.get("openai") else "미연결")
    logger.info("  Notion: %s", "연결" if status.get("notion") else "미연결")
    logger.info("  게시글: %s건 로드", status.get("posts_count"))
    logger.info("  VectorDB: %s", status.get("vectordb"))

    if not weekly_report.is_running():
        weekly_report.start()


@bot.event
async def on_message(message: discord.Message):
    if message.author == bot.user:
        return

    query, should_respond = _parse_message(message)
    if not should_respond or not query:
        return

    session_id = _get_session_id(message)

    cmd = query.strip()

    if cmd in ("리셋", "초기화", "/reset"):
        agent.reset(session_id)
        await message.reply("대화가 초기화되었습니다.")
        return

    if cmd in ("!회의시작",):
        await _handle_meeting_start(message)
        return

    if cmd in ("!회의끝",):
        await _handle_meeting_stop(message)
        return

    if cmd.startswith("!회의록"):
        await _handle_meeting_file(message)
        return

    async with message.channel.typing():
        response = await asyncio.to_thread(agent.chat, query, session_id)

    await _send_response(message, response)


# ========== 정기 작업 ==========

@tasks.loop(hours=168)
async def weekly_report():
    """주간 게시판 활동 리포트 발송"""
    if not ALLOWED_CHANNELS or not agent:
        return

    stats = get_post_stats(agent.posts)
    now = datetime.now()

    report = (
        f"[주간 리포트] {now.strftime('%Y-%m-%d')}\n"
        f"총 게시글: {stats['total_posts']}건\n"
        f"총 첨부파일: {stats['total_files']}개\n"
        f"기간: {stats['year_range']}"
    )

    for ch_id in ALLOWED_CHANNELS:
        channel = bot.get_channel(int(ch_id))
        if channel:
            await channel.send(report)


@weekly_report.before_loop
async def before_weekly():
    await bot.wait_until_ready()


# ========== 유틸리티 ==========

def _parse_message(message: discord.Message) -> tuple:
    """메시지 파싱: (query, should_respond)"""
    query = message.content

    if isinstance(message.channel, discord.DMChannel):
        return query, True

    if bot.user and bot.user.mentioned_in(message):
        query = query.replace(f"<@{bot.user.id}>", "").strip()
        return query, True

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

    for i, chunk in enumerate(_split_message(response, 2000)):
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


# ========== 회의록 핸들러 ==========

async def _handle_meeting_start(message: discord.Message):
    """음성채널 녹음 시작"""
    if _recorder.is_recording:
        await message.reply("이미 녹음 중입니다. `!회의끝`으로 종료하세요.")
        return

    if not message.author.voice or not message.author.voice.channel:
        await message.reply("먼저 음성채널에 접속한 뒤 명령해주세요.")
        return

    vc = message.author.voice.channel
    ok = await _recorder.start(vc)
    if ok:
        await message.reply(f"회의 녹음을 시작합니다. (채널: {vc.name})\n종료하려면 `!회의끝`을 입력하세요.")
    else:
        await message.reply("음성채널 연결에 실패했습니다. py-cord[voice]와 PyNaCl이 설치되어 있는지 확인하세요.")


async def _handle_meeting_stop(message: discord.Message):
    """음성채널 녹음 종료 + STT + 회의록 생성"""
    if not _recorder.is_recording:
        await message.reply("현재 녹음 중이 아닙니다.")
        return

    await message.reply("녹음을 종료하고 회의록을 생성합니다. 잠시 기다려주세요...")

    audio_data = await _recorder.stop()
    if not audio_data or len(audio_data) < 100:
        await message.reply("녹음 데이터가 없거나 너무 짧습니다.")
        return

    await _process_audio_to_minutes(message, audio_data)


async def _handle_meeting_file(message: discord.Message):
    """첨부된 음성파일로 회의록 생성"""
    if not message.attachments:
        await message.reply("음성파일(.mp3, .wav, .m4a, .ogg, .webm)을 첨부하고 `!회의록` 명령을 사용하세요.")
        return

    attachment = message.attachments[0]
    allowed = (".mp3", ".wav", ".m4a", ".ogg", ".webm")
    if not any(attachment.filename.lower().endswith(ext) for ext in allowed):
        await message.reply(f"지원 형식: {', '.join(allowed)}")
        return

    await message.reply("음성파일을 분석 중입니다...")

    audio_data = await attachment.read()
    await _process_audio_to_minutes(message, audio_data, attachment.filename)


async def _process_audio_to_minutes(message: discord.Message, audio_data: bytes, filename: str = "recording.wav"):
    """오디오 데이터 -> STT -> 회의록 생성 + 노션 저장 (공통 로직)"""
    try:
        transcript = await asyncio.to_thread(transcribe_audio, audio_data, filename)
        minutes = await asyncio.to_thread(generate_minutes, transcript)
        await _send_response(message, minutes["full_text"])

        if agent and hasattr(agent, "notion") and agent.notion.is_connected():
            try:
                title = f"회의록 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                await asyncio.to_thread(agent.notion.create_page, title, minutes["full_text"])
                await message.channel.send("회의록이 노션에 저장되었습니다.")

                # 액션 아이템 체크리스트 생성
                if minutes.get("action_items_list"):
                    try:
                        from src.notion.client import NotionClient
                        notion: NotionClient = agent.notion
                        checklist_title = f"후속조치 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                        blocks = [notion.make_to_do(item) for item in minutes["action_items_list"]]
                        notion.client.pages.create(
                            parent={"page_id": os.getenv("NOTION_ADMIN_PAGE_ID", "")},
                            properties={"title": [{"text": {"content": checklist_title}}]},
                            children=blocks,
                        )
                        await message.channel.send(
                            f"후속 조치 {len(minutes['action_items_list'])}건이 노션 체크리스트로 생성되었습니다."
                        )
                    except Exception as e:
                        logger.warning("체크리스트 생성 실패: %s", e)
            except Exception as e:
                logger.warning("노션 저장 실패: %s", e)
    except Exception as e:
        await message.reply(f"회의록 생성 실패: {e}")


# ========== 슬래시 명령어 ==========

@bot.slash_command(name="회의시작", description="음성채널 녹음을 시작합니다")
async def slash_meeting_start(ctx: discord.ApplicationContext):
    if _recorder.is_recording:
        await ctx.respond("이미 녹음 중입니다. `/회의끝`으로 종료하세요.")
        return

    if not ctx.author.voice or not ctx.author.voice.channel:
        await ctx.respond("먼저 음성채널에 접속한 뒤 명령해주세요.")
        return

    vc = ctx.author.voice.channel
    await ctx.defer()
    ok = await _recorder.start(vc)
    if ok:
        await ctx.followup.send(f"회의 녹음을 시작합니다. (채널: {vc.name})\n종료하려면 `/회의끝`을 입력하세요.")
    else:
        await ctx.followup.send("음성채널 연결에 실패했습니다.")


@bot.slash_command(name="회의끝", description="녹음을 종료하고 회의록을 생성합니다")
async def slash_meeting_stop(ctx: discord.ApplicationContext):
    if not _recorder.is_recording:
        await ctx.respond("현재 녹음 중이 아닙니다.")
        return

    await ctx.defer()
    audio_data = await _recorder.stop()

    if not audio_data or len(audio_data) < 100:
        await ctx.followup.send("녹음 데이터가 없거나 너무 짧습니다.")
        return

    try:
        transcript = await asyncio.to_thread(transcribe_audio, audio_data)
        minutes = await asyncio.to_thread(generate_minutes, transcript)

        text = minutes["full_text"]
        if len(text) > 2000:
            text = text[:1990] + "\n..."
        await ctx.followup.send(text)

        if agent and hasattr(agent, "notion") and agent.notion.is_connected():
            try:
                title = f"회의록 {datetime.now().strftime('%Y-%m-%d %H:%M')}"
                await asyncio.to_thread(agent.notion.create_page, title, minutes["full_text"])
                await ctx.followup.send("회의록이 노션에 저장되었습니다.")
            except Exception as e:
                logger.warning("노션 저장 실패: %s", e)
    except Exception as e:
        await ctx.followup.send(f"회의록 생성 실패: {e}")


def run_bot():
    """Discord 봇 실행"""
    from src import configure_logging
    configure_logging()

    token = os.getenv("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN 환경변수가 설정되지 않았습니다.")
        raise SystemExit(1)
    bot.run(token)


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    run_bot()
