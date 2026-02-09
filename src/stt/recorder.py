"""
Discord 음성채널 녹음기 (py-cord 기반)
py-cord의 voice receive API를 사용하여 실시간 녹음을 지원합니다.

사용법:
  recorder = VoiceRecorder()
  await recorder.start(voice_channel, text_channel)
  ...
  audio_data = await recorder.stop()  # WAV bytes 반환
"""
import io
import logging
import struct
import asyncio
from typing import Optional

logger = logging.getLogger(__name__)

try:
    import discord
    from discord.sinks import WaveSink
    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False


def _merge_wav_files(audio_data: dict) -> bytes:
    """
    py-cord sink의 audio_data (user_id -> AudioData)를
    단일 WAV로 병합.
    """
    if not audio_data:
        return b""

    all_pcm = io.BytesIO()
    for user_id, audio in audio_data.items():
        audio.file.seek(0)
        raw = audio.file.read()
        # WaveSink 출력은 WAV 포맷 -> PCM 데이터만 추출
        pcm = _strip_wav_header(raw)
        if pcm:
            all_pcm.write(pcm)

    pcm_data = all_pcm.getvalue()
    if not pcm_data:
        return b""

    return _pcm_to_wav(pcm_data)


def _strip_wav_header(wav_bytes: bytes) -> bytes:
    """WAV 헤더를 제거하고 PCM 데이터만 반환"""
    if len(wav_bytes) < 44:
        return wav_bytes
    # 표준 WAV: 44바이트 헤더
    if wav_bytes[:4] == b"RIFF" and wav_bytes[8:12] == b"WAVE":
        # data 청크 위치 찾기
        pos = 12
        while pos < len(wav_bytes) - 8:
            chunk_id = wav_bytes[pos:pos+4]
            chunk_size = struct.unpack_from("<I", wav_bytes, pos + 4)[0]
            if chunk_id == b"data":
                return wav_bytes[pos+8:pos+8+chunk_size]
            pos += 8 + chunk_size
        return wav_bytes[44:]
    return wav_bytes


def _pcm_to_wav(pcm_data: bytes, channels: int = 2, rate: int = 48000, bits: int = 16) -> bytes:
    """PCM 바이트 데이터에 WAV 헤더를 붙여 반환"""
    data_size = len(pcm_data)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF",
        36 + data_size,
        b"WAVE",
        b"fmt ",
        16,
        1,                              # PCM
        channels,
        rate,
        rate * channels * (bits // 8),
        channels * (bits // 8),
        bits,
        b"data",
        data_size,
    )
    return header + pcm_data


class VoiceRecorder:
    """Discord 음성채널 녹음 관리자 (py-cord voice receive)"""

    def __init__(self):
        self.voice_client: Optional[discord.VoiceClient] = None
        self._audio_data: Optional[dict] = None
        self._done_event: Optional[asyncio.Event] = None
        self.recording = False

    async def _on_recording_done(self, sink, channel, *args):
        """녹음 완료 콜백 (stop_recording 호출 시 실행)"""
        self._audio_data = sink.audio_data
        if self._done_event:
            self._done_event.set()

    async def start(self, voice_channel) -> bool:
        """음성채널에 연결하고 녹음 시작"""
        if not HAS_VOICE:
            logger.error("py-cord[voice]가 설치되지 않았습니다.")
            return False

        if self.recording:
            return False

        try:
            self._done_event = asyncio.Event()
            self._audio_data = None
            self.voice_client = await voice_channel.connect()
            self.voice_client.start_recording(
                WaveSink(),
                self._on_recording_done,
                voice_channel,
            )
            self.recording = True
            logger.info("녹음 시작: %s", voice_channel.name)
            return True
        except Exception as e:
            logger.error("음성채널 연결 실패: %s", e)
            self.recording = False
            return False

    async def stop(self) -> bytes:
        """녹음 중단 + WAV 바이트 반환"""
        if not self.recording or not self.voice_client:
            return b""

        self.recording = False

        try:
            self.voice_client.stop_recording()
            # 콜백 완료 대기 (최대 10초)
            if self._done_event:
                await asyncio.wait_for(self._done_event.wait(), timeout=10)
        except asyncio.TimeoutError:
            logger.warning("녹음 콜백 타임아웃")
        except Exception as e:
            logger.error("녹음 중단 오류: %s", e)

        try:
            await self.voice_client.disconnect()
        except Exception:
            pass

        audio_data = self._audio_data or {}
        wav_bytes = _merge_wav_files(audio_data)
        logger.info("녹음 종료: %d users, %d bytes", len(audio_data), len(wav_bytes))

        self.voice_client = None
        self._audio_data = None
        self._done_event = None
        return wav_bytes

    @property
    def is_recording(self) -> bool:
        return self.recording
