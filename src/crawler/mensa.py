"""
멘사코리아 기획위원회 게시판 크롤러
수동 로그인 후 기존 브라우저에 붙어서 크롤링
"""
import os
import sys
import time
import re
import json
import subprocess
import requests
from pathlib import Path
from typing import List, Dict, Optional, Iterable, Tuple, Set, Any
from datetime import datetime
from dataclasses import dataclass, field, asdict

if hasattr(sys.stdout, "reconfigure"):
    # Avoid Windows cp949 UnicodeEncodeError in logs (filenames/titles can include Unicode).
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import (
        TimeoutException, NoSuchElementException, WebDriverException, StaleElementReferenceException
    )
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from .base import BaseCrawler
from src.data_loader import Event, EventCategory, EventStatus


BOARD_URL = "https://www.mensakorea.org/bbs/board.php?bo_table=group_plan"
CHROME_DEBUG_PORT = 9222


def build_board_url(bo_table: str) -> str:
    """그누보드 board.php URL 생성"""
    table = (bo_table or "").strip()
    if not table:
        table = "group_plan"
    return f"https://www.mensakorea.org/bbs/board.php?bo_table={table}"


@dataclass
class MensaFile:
    """첨부파일"""
    name: str
    url: str
    size: str = ""
    local_path: str = ""


@dataclass
class MensaPost:
    """게시글 데이터"""
    id: str
    title: str
    author: str
    date: str
    views: int
    url: str
    content: str = ""
    comments: int = 0
    files: list = field(default_factory=list)  # List[MensaFile]


def launch_chrome_debug(start_url: str = BOARD_URL):
    """디버그 모드로 Chrome 실행 (수동 로그인용)"""
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]

    chrome_path = None
    for p in chrome_paths:
        if os.path.exists(p):
            chrome_path = p
            break

    if not chrome_path:
        print("Chrome not found. Start Chrome manually:")
        print(f'  chrome.exe --remote-debugging-port={CHROME_DEBUG_PORT}', flush=True)
        return False

    user_data = os.path.expandvars(r"%TEMP%\chrome_debug_profile")

    cmd = [
        chrome_path,
        f"--remote-debugging-port={CHROME_DEBUG_PORT}",
        f"--user-data-dir={user_data}",
        start_url
    ]

    subprocess.Popen(cmd)
    print(f"Chrome started in debug mode (port: {CHROME_DEBUG_PORT})", flush=True)
    print("1) Login to mensakorea.org in that browser", flush=True)
    print(f"2) Open: {start_url}", flush=True)
    return True


def attach_to_chrome() -> Optional[webdriver.Chrome]:
    """실행 중인 Chrome에 연결"""
    if not SELENIUM_AVAILABLE:
        raise ImportError("selenium 필요: uv add selenium")

    options = Options()
    options.debugger_address = f"127.0.0.1:{CHROME_DEBUG_PORT}"

    try:
        driver = webdriver.Chrome(options=options)
        # 창 제목은 한글/인코딩 이슈로 로그가 깨질 수 있어 생략
        print("Attached to Chrome.", flush=True)
        return driver
    except WebDriverException as e:
        print(f"Attach failed: {e}", flush=True)
        print(f"Make sure Chrome is running with --remote-debugging-port={CHROME_DEBUG_PORT}", flush=True)
        return None


class MensaCrawler(BaseCrawler):
    """멘사코리아 크롤러 (수동 로그인 방식)"""

    def __init__(self, board_url: str = BOARD_URL):
        self.board_url = board_url or BOARD_URL
        super().__init__(self.board_url)
        self.driver = None

    def login(self, board_url: str = "") -> bool:
        """수동 로그인된 Chrome에 연결 (지정 보드로 로그인 여부 확인)"""
        self.driver = attach_to_chrome()
        if self.driver is None:
            return False

        target = board_url or self.board_url or BOARD_URL
        return self._wait_until_logged_in(target)

    def _wait_until_logged_in(self, target_url: str, timeout_sec: int = 600) -> bool:
        """대상 URL 접근이 가능한지 확인 (login redirect면 대기)."""
        if not self.driver:
            return False

        self.driver.get(target_url)
        time.sleep(2)

        start = time.time()
        while "login" in (self.driver.current_url or "").lower():
            remain = int(timeout_sec - (time.time() - start))
            if remain <= 0:
                print("Login required. Please login in the opened browser and retry.", flush=True)
                return False
            # 사용자가 로그인하고 돌아올 시간을 줌
            print(f"Waiting for login... (remaining {remain}s)", flush=True)
            time.sleep(3)
            try:
                self.driver.get(target_url)
            except Exception:
                pass
            time.sleep(2)

        print("Login OK. Ready to crawl.", flush=True)
        return True

    def fetch_board_list(self, page: int = 1, board_url: str = None) -> List[MensaPost]:
        """게시판 목록 크롤링"""
        posts = []
        base = board_url or self.board_url or BOARD_URL
        url = f"{base}&page={page}"

        try:
            self.driver.get(url)
            time.sleep(2)

            # 그누보드 게시판 구조 탐색
            # 방법 1: 테이블 기반
            rows = self.driver.find_elements(
                By.CSS_SELECTOR,
                "#bo_list .bo_tit a, .td_subject a"
            )

            if not rows:
                # 방법 2: 리스트 기반
                rows = self.driver.find_elements(
                    By.CSS_SELECTOR,
                    ".list-board a, .bo_subject a, .board-list a"
                )

            if not rows:
                # 방법 3: 모든 링크 중 wr_id 포함된 것
                # board_url에서 bo_table 값 추출
                bo_table = "group_plan"
                bo_match = re.search(r'bo_table=([^&]+)', base)
                if bo_match:
                    bo_table = bo_match.group(1)

                all_links = self.driver.find_elements(By.TAG_NAME, "a")
                rows = [
                    a for a in all_links
                    if a.get_attribute("href")
                    and "wr_id=" in (a.get_attribute("href") or "")
                    and f"bo_table={bo_table}" in (a.get_attribute("href") or "")
                    and a.text.strip()
                ]

            seen_ids = set()
            for elem in rows:
                try:
                    # 페이지 전환/동적 로딩 타이밍에 따라 stale이 뜰 수 있음
                    # (특히 링크 목록이 많은 게시판에서 간헐적으로 발생)
                    href = elem.get_attribute("href") or ""
                    title = elem.text.strip()

                    if not title or not href or "wr_id=" not in href:
                        continue

                    # 댓글 수 제거
                    title = re.sub(r'\s*\[\d+\]\s*$', '', title)
                    title = re.sub(r'\s*\(\d+\)\s*$', '', title)

                    if not title:
                        continue

                    wr_id = re.search(r'wr_id=(\d+)', href)
                    post_id = wr_id.group(1) if wr_id else ""

                    if post_id in seen_ids:
                        continue
                    seen_ids.add(post_id)

                    posts.append(MensaPost(
                        id=post_id,
                        title=title,
                        author="",
                        date="",
                        views=0,
                        url=href
                    ))
                except StaleElementReferenceException:
                    continue
                except Exception:
                    continue

            # 부모 tr에서 작성자, 날짜, 조회수 추출 시도
            for post in posts:
                try:
                    link = self.driver.find_element(
                        By.CSS_SELECTOR,
                        f'a[href*="wr_id={post.id}"]'
                    )
                    tr = link.find_element(By.XPATH, "./ancestor::tr")
                    tds = tr.find_elements(By.TAG_NAME, "td")

                    for td in tds:
                        text = td.text.strip()
                        if re.match(r'^\d{2}-\d{2}$', text):
                            post.date = text
                        elif re.match(r'^\d{4}-\d{2}-\d{2}$', text):
                            post.date = text
                        elif text.isdigit() and int(text) < 100000:
                            post.views = int(text)

                    # 작성자 (보통 .sv_member 또는 특정 td)
                    try:
                        member = tr.find_element(
                            By.CSS_SELECTOR,
                            ".sv_member, .bo_tit_member, .td_name"
                        )
                        post.author = member.text.strip()
                    except NoSuchElementException:
                        pass
                except Exception:
                    pass

            print(f"[list] page={page} posts={len(posts)}", flush=True)
            return posts

        except Exception as e:
            print(f"[list] error: {e}", flush=True)
            return []

    def fetch_post_detail(self, post: MensaPost, download_dir: str = "data/files") -> MensaPost:
        """게시글 상세 내용 + 첨부파일 크롤링"""
        try:
            self.driver.get(post.url)
            time.sleep(1.5)

            # alert 처리
            try:
                alert = self.driver.switch_to.alert
                alert.accept()
                time.sleep(0.5)
                return post
            except Exception:
                pass

            # 본문 (.writeContents)
            for selector in [".writeContents", "#writeContents", ".wr_content"]:
                try:
                    elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    post.content = elem.text.strip()
                    if post.content:
                        break
                except NoSuchElementException:
                    continue

            # 작성자 (.member)
            if not post.author:
                for selector in [".member", ".sv_member"]:
                    try:
                        elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        post.author = elem.text.strip()
                        if post.author:
                            break
                    except NoSuchElementException:
                        continue

            # 날짜 - 페이지 소스에서 추출
            if not post.date:
                src = self.driver.page_source
                date_match = re.search(r'(\d{4}[-./]\d{2}[-./]\d{2})', src)
                if date_match:
                    post.date = date_match.group(1)

            # 첨부파일
            post.files = self._find_and_download_files(post, download_dir)

            return post

        except Exception as e:
            print(f"    detail error [{post.id}]: {e}", flush=True)
            return post

    def _find_and_download_files(self, post: MensaPost, download_dir: str) -> list:
        """첨부파일 찾기 + 다운로드 (requests 세션 쿠키 방식)"""
        files = []

        # 소스에서 file_download() 호출 추출
        src = self.driver.page_source
        # 패턴: file_download('./download.php?bo_table=group_plan&wr_id=565&no=0', '파일명.xlsx')
        pattern = r"file_download\(['\"]([^'\"]+)['\"],\s*['\"]([^'\"]+)['\"]\)"
        matches = re.findall(pattern, src)

        if not matches:
            return files

        # 쿠키 가져오기
        cookies = {c["name"]: c["value"] for c in self.driver.get_cookies()}

        # Keep per-board separation by letting caller include bo_table in download_dir.
        post_dir = os.path.join(os.path.abspath(download_dir), post.id)
        os.makedirs(post_dir, exist_ok=True)

        for dl_path, filename in matches:
            try:
                # 상대 경로 -> 절대 경로
                if dl_path.startswith("./") or dl_path.startswith("../"):
                    dl_url = "https://www.mensakorea.org/bbs/" + dl_path.lstrip("./")
                elif dl_path.startswith("http"):
                    dl_url = dl_path
                else:
                    dl_url = "https://www.mensakorea.org/bbs/" + dl_path

                # HTML 엔티티 디코딩
                dl_url = dl_url.replace("&amp;", "&")

                # 안전한 파일명
                safe_name = re.sub(r'[\\/:*?"<>|]', '_', filename)
                if not safe_name:
                    safe_name = "file"

                filepath = os.path.join(post_dir, safe_name)

                # 다운로드
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Referer": post.url
                }
                resp = requests.get(dl_url, headers=headers, cookies=cookies, timeout=60)

                if resp.status_code == 200 and len(resp.content) > 100:
                    with open(filepath, "wb") as f:
                        f.write(resp.content)

                    size_kb = os.path.getsize(filepath) / 1024
                    size_str = f"{size_kb:.1f}KB" if size_kb < 1024 else f"{size_kb/1024:.1f}MB"

                    mf = MensaFile(name=filename, url=dl_url, size=size_str, local_path=filepath)
                    files.append(mf)
                    print(f"    download ok: {safe_name} ({size_str})", flush=True)
                else:
                    mf = MensaFile(name=filename, url=dl_url, size="", local_path="")
                    files.append(mf)
                    print(f"    download failed: status={resp.status_code}", flush=True)

            except Exception as e:
                print(f"    download error: {e}", flush=True)
                mf = MensaFile(name=filename, url="", size="", local_path="")
                files.append(mf)

        return files

    def fetch_all_posts(self, max_pages: int = 5, with_detail: bool = True) -> List[MensaPost]:
        """전체 게시글 크롤링"""
        all_posts = []

        for page in range(1, max_pages + 1):
            posts = self.fetch_board_list(page)
            if not posts:
                print(f"페이지 {page}: 게시글 없음, 중단")
                break
            all_posts.extend(posts)
            time.sleep(0.5)

        if with_detail:
            total = len(all_posts)
            for i, post in enumerate(all_posts):
                print(f"  상세 크롤링 [{i+1}/{total}] {post.title[:30]}...")
                self.fetch_post_detail(post)
                time.sleep(0.5)

        print(f"총 {len(all_posts)}개 게시글 수집 완료")
        return all_posts

    def fetch_events(self, start_date=None, end_date=None) -> List[Event]:
        """게시글을 Event 형식으로 변환"""
        posts = self.fetch_all_posts()
        events = []

        for post in posts:
            event_date = self._parse_date(post)
            category = self._infer_category(post.title)

            event = Event(
                id=post.id,
                title=post.title,
                category=category,
                status=EventStatus.PLANNED,
                start_date=event_date,
                end_date=event_date,
                location=self._extract_location(post.content),
                manager=post.author,
                description=post.content
            )
            events.append(event)

        return events

    def fetch_event_detail(self, event_id: str) -> Event:
        raise NotImplementedError("fetch_event_detail는 아직 구현되지 않았습니다.")

    def close(self):
        """연결 해제 (브라우저는 닫지 않음)"""
        self.driver = None
        print("연결 해제 (브라우저는 유지됨)")

    def save_to_json(self, posts: List[MensaPost], path: str = "data/crawled.json"):
        """크롤링 결과 JSON 저장"""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        data = []
        for p in posts:
            d = asdict(p)
            # MensaFile -> dict 변환
            d["files"] = [asdict(f) if isinstance(f, MensaFile) else f for f in (p.files or [])]
            data.append(d)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"저장 완료: {path} ({len(posts)}건)")

    @staticmethod
    def load_from_json(path: str = "data/crawled.json") -> List[MensaPost]:
        """JSON에서 불러오기"""
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        posts = []
        for d in data:
            files_raw = d.pop("files", [])
            post = MensaPost(**d)
            post.files = [
                MensaFile(**f) if isinstance(f, dict) else f
                for f in files_raw
            ]
            posts.append(post)
        return posts

    # ========== 내부 유틸 ==========

    @staticmethod
    def _parse_date(post: MensaPost) -> datetime:
        """날짜 파싱"""
        # 게시글 날짜 필드
        if post.date:
            for fmt in ["%Y-%m-%d", "%y-%m-%d", "%m-%d"]:
                try:
                    d = datetime.strptime(post.date, fmt)
                    if d.year < 2000:
                        d = d.replace(year=datetime.now().year)
                    return d
                except ValueError:
                    continue

        # 제목/본문에서 날짜 추출
        text = f"{post.title} {post.content}"
        patterns = [
            r'(\d{4})[./\-](\d{1,2})[./\-](\d{1,2})',
            r'(\d{1,2})[./](\d{1,2})',
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                groups = match.groups()
                try:
                    if len(groups) == 3:
                        return datetime(int(groups[0]), int(groups[1]), int(groups[2]))
                    elif len(groups) == 2:
                        return datetime(datetime.now().year, int(groups[0]), int(groups[1]))
                except ValueError:
                    continue

        return datetime.now()

    @staticmethod
    def _infer_category(title: str) -> EventCategory:
        """제목에서 카테고리 추론"""
        t = title.lower()
        if any(k in t for k in ["정모", "정기", "월례"]):
            return EventCategory.MEETING
        if "세미나" in t or "강연" in t or "특강" in t:
            return EventCategory.SEMINAR
        if "워크샵" in t or "워크숍" in t:
            return EventCategory.WORKSHOP
        if any(k in t for k in ["네트워킹", "번개", "모임", "친목"]):
            return EventCategory.NETWORKING
        if any(k in t for k in ["대회", "경진", "퀴즈", "게임"]):
            return EventCategory.COMPETITION
        if any(k in t for k in ["축제", "페스티벌", "파티"]):
            return EventCategory.FESTIVAL
        if "컨퍼런스" in t:
            return EventCategory.CONFERENCE
        return EventCategory.OTHER

    @staticmethod
    def _extract_location(content: str) -> str:
        """본문에서 장소 추출"""
        if not content:
            return ""
        patterns = [
            r'(?:장소|위치|place)\s*[:：]\s*(.+)',
            r'(?:장소|위치)\s*[:\-]\s*(.+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return match.group(1).strip()[:50]
        return ""


def _read_jsonl(path: str) -> List[Dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        return []
    out: List[Dict[str, Any]] = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                continue
    return out


def _write_jsonl(path: str, items: Iterable[Dict[str, Any]]):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")


def export_board_to_rag_jsonl(
    bo_table: str,
    rag_jsonl_path: str = "data/notion_rag.jsonl",
    *,
    start_page: int = 1,
    max_pages: int = 30,
    with_detail: bool = True,
) -> Dict[str, int]:
    """로그인된 Chrome 권한으로 게시판을 크롤링하고 RAG JSONL에 병합."""
    board_url = build_board_url(bo_table)

    existing = _read_jsonl(rag_jsonl_path)
    seen: Set[Tuple[str, str]] = set()
    kept: List[Dict[str, Any]] = []
    for item in existing:
        src = str(item.get("source") or "")
        url = str(item.get("url") or "")
        if src and url:
            seen.add((src, url))
        kept.append(item)

    # Chrome 디버그 모드 실행(없으면) -> attach
    print("=" * 50, flush=True)
    print(f"Mensa RAG crawl (bo_table={bo_table}, start_page={start_page}, max_pages={max_pages})", flush=True)
    print("=" * 50, flush=True)
    print("[1] Chrome debug / login", flush=True)
    if attach_to_chrome() is None:
        launch_chrome_debug(start_url=board_url)

    print("[2] Attach + login check", flush=True)
    crawler = MensaCrawler(board_url=board_url)
    if not crawler.login(board_url=board_url):
        return {"kept": len(kept), "added": 0}

    print("[3] Crawl", flush=True)
    added = 0
    if start_page < 1:
        start_page = 1
    end_page = start_page + max_pages - 1

    for page in range(start_page, end_page + 1):
        posts = crawler.fetch_board_list(page=page, board_url=board_url)
        if not posts:
            break
        print(f"[page {page}] posts={len(posts)} added={added}", flush=True)

        for post in posts:
            if with_detail:
                try:
                    # Separate downloads by board to avoid wr_id collisions between boards.
                    crawler.fetch_post_detail(post, download_dir=os.path.join("data", "files", bo_table))
                except Exception:
                    pass

            files_meta = []
            for f in (post.files or []):
                if isinstance(f, MensaFile):
                    files_meta.append(asdict(f))
                elif isinstance(f, dict):
                    files_meta.append(f)

            doc = {
                "source": f"mensa_{bo_table}",
                "id": f"{bo_table}:{post.id}",
                "url": post.url,
                "title": post.title,
                "author": post.author,
                "date": post.date,
                "text": (post.content or "").strip(),
                "files": files_meta,
            }
            key = (doc["source"], doc["url"])
            if key in seen:
                continue
            seen.add(key)
            kept.append(doc)
            added += 1

    crawler.close()
    _write_jsonl(rag_jsonl_path, kept)
    return {"kept": len(kept), "added": added}


def run_crawl():
    """크롤링 실행 스크립트"""
    from dotenv import load_dotenv
    load_dotenv()

    print("=" * 50)
    print("멘사코리아 기획위원회 게시판 크롤러")
    print("=" * 50)

    # 1. Chrome 실행
    print("\n[1] Chrome 디버그 모드 실행")
    launched = launch_chrome_debug()

    if launched:
        print("\n브라우저에서 로그인하세요.")
        input("로그인 완료 후 Enter를 누르세요... ")

    # 2. 연결
    print("\n[2] Chrome에 연결 중...")
    crawler = MensaCrawler()
    if not crawler.login():
        print("연결 실패. 종료합니다.")
        return

    # 3. 크롤링
    print("\n[3] 크롤링 시작...")
    posts = crawler.fetch_all_posts(max_pages=10, with_detail=True)

    if not posts:
        print("게시글을 찾지 못했습니다.")
        crawler.close()
        return

    # 4. 저장
    print("\n[4] 결과 저장...")
    crawler.save_to_json(posts)

    # 5. 요약
    print("\n" + "=" * 50)
    print(f"크롤링 완료: {len(posts)}건")
    print("=" * 50)
    for i, post in enumerate(posts[:5]):
        print(f"  {i+1}. [{post.date}] {post.title} - {post.author}")
    if len(posts) > 5:
        print(f"  ... 외 {len(posts) - 5}건")

    # 6. 벡터 DB 저장
    try:
        from src.vectordb import VectorStore
        store = VectorStore()
        store.add_posts_batch([
            {
                "id": p.id,
                "title": p.title,
                "content": p.content,
                "author": p.author,
                "date": p.date,
                "url": p.url
            }
            for p in posts
        ])
        print(f"\n벡터 DB 저장 완료: {store.get_stats()}")
    except Exception as e:
        print(f"\n벡터 DB 저장 실패: {e}")

    crawler.close()
    print("\n완료!")


if __name__ == "__main__":
    import sys

    mode = sys.argv[1].strip() if len(sys.argv) > 1 else ""
    if mode == "rag":
        # usage:
        #   py -3 -m src.crawler.mensa rag <bo_table> [start_page] [max_pages] [--no-detail]
        bo_table = sys.argv[2].strip() if len(sys.argv) > 2 else "sig"
        start_page = int(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3].isdigit() else 1
        max_pages = int(sys.argv[4]) if len(sys.argv) > 4 and sys.argv[4].isdigit() else 30
        with_detail = "--no-detail" not in sys.argv

        result = export_board_to_rag_jsonl(
            bo_table,
            "data/notion_rag.jsonl",
            start_page=start_page,
            max_pages=max_pages,
            with_detail=with_detail,
        )
        print(f"Done: kept={result['kept']} added={result['added']} path=data/notion_rag.jsonl", flush=True)
    elif mode == "sig_rag":
        # backwards compatible
        result = export_board_to_rag_jsonl("sig", "data/notion_rag.jsonl", start_page=1, max_pages=30, with_detail=True)
        print(f"Done: kept={result['kept']} added={result['added']} path=data/notion_rag.jsonl", flush=True)
    else:
        run_crawl()
