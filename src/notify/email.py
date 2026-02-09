"""
이메일 알림 클라이언트
SMTP 기반. 환경변수: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SMTP_FROM
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Optional

logger = logging.getLogger(__name__)

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)


def send_email(
    to: str,
    subject: str,
    body: str,
    *,
    html: bool = False,
    cc: Optional[List[str]] = None,
) -> bool:
    """
    단건 이메일 발송.

    Args:
        to: 수신자 이메일
        subject: 제목
        body: 본문 (text 또는 html)
        html: HTML 여부
        cc: 참조 목록

    Returns:
        성공 여부
    """
    if not SMTP_USER or not SMTP_PASS:
        logger.warning("SMTP 설정 미완료. 이메일 발송 건너뜀.")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"] = SMTP_FROM
    msg["To"] = to
    msg["Subject"] = subject
    if cc:
        msg["Cc"] = ", ".join(cc)

    content_type = "html" if html else "plain"
    msg.attach(MIMEText(body, content_type, "utf-8"))

    recipients = [to] + (cc or [])

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_FROM, recipients, msg.as_string())
        logger.info("이메일 발송 완료: %s -> %s", subject, to)
        return True
    except Exception as e:
        logger.error("이메일 발송 실패: %s", e)
        return False


def send_bulk_email(
    recipients: List[str],
    subject: str,
    body: str,
    *,
    html: bool = False,
) -> int:
    """
    대량 이메일 발송.

    Returns:
        성공 건수
    """
    success = 0
    for to in recipients:
        if send_email(to, subject, body, html=html):
            success += 1
    return success


# ========== 편의 함수 ==========


def send_event_invite(to: str, event_title: str, date: str, location: str, description: str = ""):
    """행사 초대 이메일"""
    body = f"""
    <h2>{event_title}</h2>
    <p><strong>일시:</strong> {date}</p>
    <p><strong>장소:</strong> {location}</p>
    <p>{description}</p>
    """
    return send_email(to, f"[기획위] {event_title} 초대", body, html=True)


def send_weekly_report_email(to: str, report: dict):
    """주간 리포트 이메일"""
    lines = [
        f"<h2>주간 리포트 ({report.get('period', '')})</h2>",
        f"<p>완료 행사: {report.get('completed_events', 0)}건</p>",
        f"<p>예정 행사: {report.get('upcoming_events', 0)}건</p>",
        f"<p>미완료 태스크: {report.get('pending_tasks', 0)}건</p>",
        f"<p>기한 초과: {report.get('overdue_tasks', 0)}건</p>",
    ]
    body = "\n".join(lines)
    return send_email(to, f"[기획위] 주간 리포트 ({report.get('period', '')})", body, html=True)
