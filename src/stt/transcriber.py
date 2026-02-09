"""
STT (Speech-to-Text) + 회의록 자동생성
OpenAI Whisper API를 사용한 음성 텍스트 변환 + GPT 기반 회의록 구조화
"""
import os
import io
import logging
from pathlib import Path
from typing import Dict, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


def transcribe_audio(
    audio_data: bytes,
    filename: str = "recording.wav",
    language: str = "ko",
) -> str:
    """
    Whisper API로 음성을 텍스트로 변환.

    Args:
        audio_data: 오디오 바이트 데이터 (wav/mp3/m4a 등)
        filename: 파일명 (확장자로 포맷 감지)
        language: 언어 코드

    Returns:
        변환된 텍스트
    """
    client = _get_client()

    audio_file = io.BytesIO(audio_data)
    audio_file.name = filename

    try:
        result = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language,
            response_format="text",
        )
        logger.info("STT 변환 완료: %d bytes -> %d chars", len(audio_data), len(result))
        return result
    except Exception as e:
        logger.error("STT 변환 실패: %s", e)
        raise


def transcribe_file(file_path: str, language: str = "ko") -> str:
    """파일 경로로부터 STT 변환"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"파일 없음: {file_path}")

    with open(path, "rb") as f:
        return transcribe_audio(f.read(), filename=path.name, language=language)


MINUTES_PROMPT = """다음은 회의 녹음의 텍스트 변환 결과입니다. 이것을 구조화된 회의록으로 정리해주세요.

반드시 아래 형식을 따르세요:

## 회의 요약
(전체 회의 내용을 3문장 이내로 요약)

## 참석자
(텍스트에서 식별 가능한 참석자 이름/역할 나열. 식별 불가시 "식별 불가" 표기)

## 안건 및 논의 사항
(주요 논의 항목을 번호 매겨 정리)

## 결정 사항
(회의에서 확정된 사항 나열. 없으면 "없음")

## 후속 조치 (Action Items)
(누가 / 무엇을 / 언제까지 형식으로 정리. 없으면 "없음")

---
녹음 텍스트:
"""


def generate_minutes(transcript: str) -> Dict[str, str]:
    """
    STT 텍스트로부터 구조화된 회의록 생성 (비스트리밍).

    Returns:
        {"full_text": "...", "summary": "...", "action_items": "...", "action_items_list": [...]}
    """
    client = _get_client()

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 기획위원회 회의록 작성 전문가입니다. 한국어로 답변합니다."},
                {"role": "user", "content": f"{MINUTES_PROMPT}\n{transcript}"},
            ],
            temperature=0.3,
            max_tokens=4000,
        )
        full_text = response.choices[0].message.content or ""

        summary = _extract_section(full_text, "회의 요약")
        action_items = _extract_section(full_text, "후속 조치")
        action_items_list = _parse_action_items(action_items)

        return {
            "full_text": full_text,
            "summary": summary,
            "action_items": action_items,
            "action_items_list": action_items_list,
            "transcript": transcript,
        }
    except Exception as e:
        logger.error("회의록 생성 실패: %s", e)
        raise


def generate_minutes_stream(transcript: str):
    """
    STT 텍스트로부터 회의록을 스트리밍 생성.
    yield로 텍스트 청크를 반환한다. (Generator[str, None, None])
    """
    client = _get_client()

    try:
        stream = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "당신은 기획위원회 회의록 작성 전문가입니다. 한국어로 답변합니다."},
                {"role": "user", "content": f"{MINUTES_PROMPT}\n{transcript}"},
            ],
            temperature=0.3,
            max_tokens=4000,
            stream=True,
        )
        for chunk in stream:
            delta = chunk.choices[0].delta if chunk.choices else None
            if delta and delta.content:
                yield delta.content
    except Exception as e:
        logger.error("회의록 스트리밍 생성 실패: %s", e)
        raise


def _parse_action_items(text: str) -> list:
    """액션 아이템 텍스트를 개별 항목 리스트로 변환"""
    if not text or text.strip() == "없음":
        return []
    items = []
    for line in text.split("\n"):
        line = line.strip()
        if not line:
            continue
        # "- ", "1. ", "* " 등 접두사 제거
        for prefix in ("- ", "* ", "1. ", "2. ", "3. ", "4. ", "5. ", "6. ", "7. ", "8. ", "9. ", "10. "):
            if line.startswith(prefix):
                line = line[len(prefix):]
                break
        if line and line != "없음":
            items.append(line)
    return items


def _extract_section(text: str, section_name: str) -> str:
    """마크다운 텍스트에서 특정 섹션 추출"""
    lines = text.split("\n")
    collecting = False
    result = []

    for line in lines:
        if section_name in line and line.strip().startswith("#"):
            collecting = True
            continue
        if collecting:
            if line.strip().startswith("#"):
                break
            result.append(line)

    return "\n".join(result).strip()
