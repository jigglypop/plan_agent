"""
멘사코리아 기획위원회 게시판 크롤러
로그인 필요
"""
import os
import time
import re
from typing import List, Dict, Optional
from datetime import datetime
from dataclasses import dataclass

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, NoSuchElementException
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

from .base import BaseCrawler
from src.data import Event, EventCategory, EventStatus


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


class MensaCrawler(BaseCrawler):
    """멘사코리아 크롤러"""
    
    BASE_URL = "https://www.mensakorea.org"
    LOGIN_URL = "https://www.mensakorea.org/bbs/login.php"
    BOARD_URL = "https://www.mensakorea.org/bbs/board.php?bo_table=group_plan"
    
    def __init__(self, username: str = None, password: str = None, headless: bool = True):
        super().__init__(self.BASE_URL)
        self.username = username or os.getenv("MENSA_USERNAME")
        self.password = password or os.getenv("MENSA_PASSWORD")
        self.headless = headless
        self.driver = None
        self.logged_in = False
    
    def _init_driver(self):
        """WebDriver 초기화"""
        if not SELENIUM_AVAILABLE:
            raise ImportError("selenium이 설치되지 않았습니다. pip install selenium")
        
        options = Options()
        if self.headless:
            options.add_argument("--headless")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        self.driver = webdriver.Chrome(options=options)
        self.driver.implicitly_wait(10)
    
    def login(self) -> bool:
        """로그인"""
        if not self.username or not self.password:
            print("로그인 정보가 없습니다. .env에 MENSA_USERNAME, MENSA_PASSWORD를 설정하세요.")
            return False
        
        if self.driver is None:
            self._init_driver()
        
        try:
            self.driver.get(self.LOGIN_URL)
            time.sleep(2)
            
            # 아이디 입력
            username_field = self.driver.find_element(By.NAME, "mb_id")
            username_field.clear()
            username_field.send_keys(self.username)
            
            # 비밀번호 입력
            password_field = self.driver.find_element(By.NAME, "mb_password")
            password_field.clear()
            password_field.send_keys(self.password)
            
            # 로그인 버튼 클릭
            login_button = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], input[type='submit']")
            login_button.click()
            
            time.sleep(3)
            
            # 로그인 성공 확인
            if "login" not in self.driver.current_url.lower():
                self.logged_in = True
                print("로그인 성공!")
                return True
            else:
                print("로그인 실패")
                return False
                
        except Exception as e:
            print(f"로그인 에러: {e}")
            return False
    
    def fetch_board_list(self, page: int = 1) -> List[MensaPost]:
        """게시판 목록 크롤링"""
        if not self.logged_in:
            if not self.login():
                return []
        
        posts = []
        url = f"{self.BOARD_URL}&page={page}"
        
        try:
            self.driver.get(url)
            time.sleep(2)
            
            # 게시글 목록 찾기 (그누보드 구조)
            rows = self.driver.find_elements(By.CSS_SELECTOR, ".bo_tit a, .td_subject a, li.list-item a")
            
            if not rows:
                # 다른 선택자 시도
                rows = self.driver.find_elements(By.XPATH, "//table//tr[contains(@class, 'bo_notice') or contains(@class, 'bg')]")
            
            for row in rows:
                try:
                    # 제목과 링크
                    link = row.get_attribute("href") if row.tag_name == "a" else row.find_element(By.TAG_NAME, "a").get_attribute("href")
                    title = row.text.strip() if row.tag_name == "a" else row.find_element(By.CSS_SELECTOR, ".bo_tit a, .td_subject a").text.strip()
                    
                    if not title or not link:
                        continue
                    
                    # ID 추출
                    wr_id_match = re.search(r'wr_id=(\d+)', link)
                    post_id = wr_id_match.group(1) if wr_id_match else ""
                    
                    posts.append(MensaPost(
                        id=post_id,
                        title=title,
                        author="",
                        date="",
                        views=0,
                        url=link
                    ))
                except Exception as e:
                    continue
            
            # 테이블 형태로 재시도
            if not posts:
                table_rows = self.driver.find_elements(By.CSS_SELECTOR, "table tbody tr, .list-body li")
                for row in table_rows:
                    try:
                        cols = row.find_elements(By.TAG_NAME, "td")
                        if len(cols) < 3:
                            continue
                        
                        title_elem = row.find_element(By.CSS_SELECTOR, "a")
                        link = title_elem.get_attribute("href")
                        title = title_elem.text.strip()
                        
                        wr_id_match = re.search(r'wr_id=(\d+)', link)
                        post_id = wr_id_match.group(1) if wr_id_match else ""
                        
                        # 작성자, 날짜 추출 시도
                        author = ""
                        date = ""
                        views = 0
                        
                        for col in cols:
                            text = col.text.strip()
                            if re.match(r'\d{2}-\d{2}', text) or re.match(r'\d{4}-\d{2}-\d{2}', text):
                                date = text
                            elif text.isdigit():
                                views = int(text)
                        
                        posts.append(MensaPost(
                            id=post_id,
                            title=title,
                            author=author,
                            date=date,
                            views=views,
                            url=link
                        ))
                    except Exception:
                        continue
            
            print(f"페이지 {page}: {len(posts)}개 게시글 발견")
            return posts
            
        except Exception as e:
            print(f"목록 크롤링 에러: {e}")
            return []
    
    def fetch_post_detail(self, post: MensaPost) -> MensaPost:
        """게시글 상세 내용 크롤링"""
        if not self.logged_in:
            if not self.login():
                return post
        
        try:
            self.driver.get(post.url)
            time.sleep(2)
            
            # 본문 내용 추출
            content_selectors = [
                "#bo_v_con",
                ".bo_v_con",
                "#bo_v_atc",
                ".view-content",
                ".content",
                "article"
            ]
            
            for selector in content_selectors:
                try:
                    content_elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                    post.content = content_elem.text.strip()
                    break
                except NoSuchElementException:
                    continue
            
            # 작성자 추출
            try:
                author_elem = self.driver.find_element(By.CSS_SELECTOR, ".sv_member, .bo_v_info .member, .writer")
                post.author = author_elem.text.strip()
            except NoSuchElementException:
                pass
            
            # 날짜 추출
            try:
                date_elem = self.driver.find_element(By.CSS_SELECTOR, ".bo_v_info time, .date, .sv_date")
                post.date = date_elem.text.strip()
            except NoSuchElementException:
                pass
            
            return post
            
        except Exception as e:
            print(f"상세 크롤링 에러: {e}")
            return post
    
    def fetch_all_posts(self, max_pages: int = 5) -> List[MensaPost]:
        """전체 게시글 크롤링"""
        all_posts = []
        
        for page in range(1, max_pages + 1):
            posts = self.fetch_board_list(page)
            if not posts:
                break
            all_posts.extend(posts)
            time.sleep(1)  # 서버 부하 방지
        
        print(f"총 {len(all_posts)}개 게시글 수집")
        return all_posts
    
    def fetch_events(self, start_date=None, end_date=None) -> List[Event]:
        """게시글을 Event 형식으로 변환"""
        posts = self.fetch_all_posts()
        events = []
        
        for post in posts:
            # 제목에서 날짜 추출 시도
            date_match = re.search(r'(\d{1,2})[./](\d{1,2})', post.title)
            if date_match:
                month = int(date_match.group(1))
                day = int(date_match.group(2))
                year = datetime.now().year
                try:
                    event_date = datetime(year, month, day)
                except ValueError:
                    event_date = datetime.now()
            else:
                event_date = datetime.now()
            
            # 카테고리 추론
            title_lower = post.title.lower()
            if "정모" in title_lower or "정기" in title_lower:
                category = EventCategory.MEETING
            elif "세미나" in title_lower:
                category = EventCategory.SEMINAR
            elif "워크샵" in title_lower:
                category = EventCategory.WORKSHOP
            elif "네트워킹" in title_lower or "번개" in title_lower:
                category = EventCategory.NETWORKING
            else:
                category = EventCategory.OTHER
            
            event = Event(
                id=post.id,
                title=post.title,
                category=category,
                status=EventStatus.PLANNED,
                start_date=event_date,
                end_date=event_date,
                location="",
                manager=post.author,
                description=post.content
            )
            events.append(event)
        
        return events
    
    def fetch_event_detail(self, event_id: str) -> Event:
        """이벤트 상세"""
        # 구현 필요
        return None
    
    def close(self):
        """브라우저 종료"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.logged_in = False


def test_crawler():
    """크롤러 테스트"""
    from dotenv import load_dotenv
    load_dotenv()
    
    crawler = MensaCrawler(headless=False)  # 디버깅용 headless=False
    
    try:
        if crawler.login():
            posts = crawler.fetch_board_list(1)
            for post in posts[:5]:
                print(f"- {post.title} ({post.url})")
                
                # 상세 내용 가져오기
                detailed = crawler.fetch_post_detail(post)
                print(f"  내용: {detailed.content[:100]}..." if detailed.content else "  내용 없음")
    finally:
        crawler.close()


if __name__ == "__main__":
    test_crawler()
