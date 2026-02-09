"""
카카오 비즈메시지 알림톡 클라이언트
환경변수: KAKAO_REST_KEY, KAKAO_SENDER_KEY, KAKAO_TEMPLATE_*
"""
import os
import logging
from typing import List, Dict, Optional

import requests

logger = logging.getLogger(__name__)

API_URL = "https://kapi.kakao.com/v2/api/talk/memo/default/send"
BIZ_URL = "https://kapi.kakao.com/v1/api/talk/friends/message/default/send"

_REST_KEY = os.getenv("KAKAO_REST_KEY", "")
_SENDER_KEY = os.getenv("KAKAO_SENDER_KEY", "")


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"KakaoAK {_REST_KEY}",
        "Content-Type": "application/x-www-form-urlencoded",
    }


def send_alimtalk(
    phone: str,
    template_code: str,
    variables: Dict[str, str],
    *,
    button_url: str = "",
) -> Dict:
    """
    단건 알림톡 발송.
    카카오 비즈메시지 API를 통해 알림톡을 전송합니다.
    실제 발송을 위해서는 카카오 비즈니스 채널 가입 + 템플릿 등록이 필요합니다.

    Args:
        phone: 수신자 전화번호 (01012345678 형식)
        template_code: 등록된 템플릿 코드
        variables: 템플릿 변수 딕셔너리
        button_url: 링크 버튼 URL (선택)

    Returns:
        API 응답 딕셔너리
    """
    if not _REST_KEY or not _SENDER_KEY:
        logger.warning("카카오 API 키 미설정. 알림톡 발송 건너뜀.")
        return {"status": "skipped", "reason": "api_key_not_set"}

    payload = {
        "senderkey": _SENDER_KEY,
        "template_code": template_code,
        "receiver_num": phone,
        "message": _render_template(variables),
    }

    if button_url:
        payload["button"] = [{"name": "확인하기", "type": "WL", "url_mobile": button_url}]

    try:
        resp = requests.post(
            "https://kapi.kakao.com/v2/api/talk/memo/default/send",
            headers=_headers(),
            data=payload,
            timeout=10,
        )
        result = resp.json()
        if resp.status_code != 200:
            logger.error("알림톡 발송 실패: %s", result)
        return result
    except Exception as e:
        logger.error("알림톡 발송 오류: %s", e)
        return {"status": "error", "error": str(e)}


def send_bulk_alimtalk(
    recipients: List[Dict],
    template_code: str,
    variables: Dict[str, str],
) -> List[Dict]:
    """
    대량 알림톡 발송.

    Args:
        recipients: [{"phone": "01012345678", "name": "홍길동"}, ...]
        template_code: 등록된 템플릿 코드
        variables: 공통 템플릿 변수

    Returns:
        각 수신자별 발송 결과 목록
    """
    results = []
    for r in recipients:
        merged = {**variables, "name": r.get("name", "")}
        result = send_alimtalk(r["phone"], template_code, merged)
        results.append({"phone": r["phone"], **result})
    return results


def _render_template(variables: Dict[str, str]) -> str:
    """변수를 치환한 메시지 텍스트 생성"""
    parts = []
    for k, v in variables.items():
        parts.append(f"{k}: {v}")
    return "\n".join(parts)


# ========== 알림 타입별 편의 함수 ==========


def notify_event_reminder(phone: str, event_title: str, days: int, location: str = ""):
    """행사 리마인더 알림톡"""
    return send_alimtalk(
        phone,
        os.getenv("KAKAO_TEMPLATE_REMINDER", "REMINDER_001"),
        {
            "행사명": event_title,
            "D-Day": f"D-{days}" if days > 0 else "오늘",
            "장소": location or "미정",
        },
    )


def notify_task_deadline(phone: str, task_title: str, due_date: str, assignee: str = ""):
    """태스크 마감 알림톡"""
    return send_alimtalk(
        phone,
        os.getenv("KAKAO_TEMPLATE_TASK", "TASK_001"),
        {
            "태스크": task_title,
            "마감일": due_date,
            "담당자": assignee or "미배정",
        },
    )


def notify_new_assignment(phone: str, task_title: str, event_title: str = ""):
    """새 태스크 배정 알림톡"""
    return send_alimtalk(
        phone,
        os.getenv("KAKAO_TEMPLATE_ASSIGN", "ASSIGN_001"),
        {
            "태스크": task_title,
            "행사명": event_title or "-",
        },
    )
