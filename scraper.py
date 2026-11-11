import os
import re
import json
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

def clean_filename(title: str, max_len: int = 50) -> str:
    """파일명으로 쓸 수 없는 특수문자 제거 및 길이 제한"""
    cleaned = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    cleaned = re.sub(r'\s+', "_", cleaned)
    return cleaned[:max_len] if cleaned else "extracted_material"

def format_seconds(seconds: float) -> str:
    """초 단위를 HH:MM:SS 또는 MM:SS 형태의 타임코드로 변환"""
    sec = int(seconds)
    hours = sec // 3600
    minutes = (sec % 3600) // 60
    rem_sec = sec % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{rem_sec:02d}"
    return f"{minutes:02d}:{rem_sec:02d}"

def extract_youtube_video_id(url: str) -> str:
    """유튜브 URL에서 비디오 ID 추출"""
    patterns = [
        r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
        r'(?:embed\/|shorts\/)([0-9A-Za-z_-]{11})',
        r'youtu\.be\/([0-9A-Za-z_-]{11})'
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return ""

def get_youtube_title(video_id: str) -> str:
    """유튜브 oEmbed API를 이용해 비디오 제목 가져오기"""
    oembed_url = f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json"
    try:
        res = requests.get(oembed_url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            return res.json().get("title", f"YouTube_{video_id}")
    except Exception:
        pass
    return f"YouTube_{video_id}"

def scrape_youtube(url: str, output_dir: str = "output") -> dict:
    """유튜브 자막/대본 추출 (타임코드 버전 + 줄글 대본 버전)"""
    video_id = extract_youtube_video_id(url)
    if not video_id:
        return {"ok": False, "error": "유효한 유튜브 URL이 아닙니다."}

    title = get_youtube_title(video_id)
    os.makedirs(output_dir, exist_ok=True)

    try:
        api = YouTubeTranscriptApi()
        # 유튜브 자막 목록 가져오기 (한국어 최우선, 영어 차선)
        transcript_list = api.list(video_id)
        transcript = None
        lang_code = "unknown"

        # 1. 수동 작성된 자막 우선 탐색
        try:
            transcript = transcript_list.find_manually_created_transcript(['ko', 'ko-KR', 'en'])
            lang_code = transcript.language_code
        except Exception:
            pass

        # 2. 자동 생성 자막 탐색
        if not transcript:
            try:
                transcript = transcript_list.find_generated_transcript(['ko', 'ko-KR', 'en'])
                lang_code = transcript.language_code
            except Exception:
                # 사용 가능한 아무 자막이나 가져오기
                for t in transcript_list:
                    transcript = t
                    lang_code = t.language_code
                    break

        if not transcript:
            return {"ok": False, "error": "해당 영상에 지원되는 자막/스크립트가 없습니다."}

        entries = transcript.fetch()

        # 타임코드 버전 & 순수 줄글 버전 생성
        timestamped_lines = []
        plain_text_lines = []

        for entry in entries:
            text = getattr(entry, 'text', None)
            if text is None and isinstance(entry, dict):
                text = entry.get('text', '')
            text = (text or '').strip()
            if not text:
                continue

            start_val = getattr(entry, 'start', None)
            if start_val is None and isinstance(entry, dict):
                start_val = entry.get('start', 0.0)
            start_time = format_seconds(start_val or 0.0)

            timestamped_lines.append(f"[{start_time}] {text}")
            plain_text_lines.append(text)

        full_plain_text = " ".join(plain_text_lines)

        # 마크다운 파일 저장
        filename = f"{clean_filename(title)}_{video_id}.md"
        filepath = os.path.join(output_dir, filename)

        md_content = f"""# {title}

- **출처 URL**: https://www.youtube.com/watch?v={video_id}
- **자막 언어**: {lang_code}
- **수집 일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 📝 영상 대본 요약 (줄글 읽기용)

{full_plain_text}

---

## ⏱️ 타임코드별 스크립트 (편집 및 싱크 맞추기용)

```text
""" + "\n".join(timestamped_lines) + """
```
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        return {
            "ok": True,
            "type": "youtube",
            "title": title,
            "video_id": video_id,
            "language": lang_code,
            "filepath": filepath,
            "total_lines": len(timestamped_lines),
            "preview": full_plain_text[:300] + "..." if len(full_plain_text) > 300 else full_plain_text
        }

    except TranscriptsDisabled:
        return {"ok": False, "error": "해당 영상은 자막 기능이 비활성화되어 있습니다."}
    except NoTranscriptFound:
        return {"ok": False, "error": "해당 영상에 등록된 자막을 찾을 수 없습니다."}
    except Exception as e:
        return {"ok": False, "error": f"자막 추출 중 오류 발생: {str(e)}"}

def scrape_web_article(url: str, output_dir: str = "output") -> dict:
    """웹 기사, 블로그, 포스트 본문 및 자료 텍스트 자동 스크랩"""
    os.makedirs(output_dir, exist_ok=True)
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        res.encoding = res.apparent_encoding
        if res.status_code != 200:
            return {"ok": False, "error": f"웹페이지 접근 실패 (상태 코드: {res.status_code})"}

        soup = BeautifulSoup(res.text, "html.parser")

        # 1. 불필요한 태그 제거 (스크립트, 스타일, 네비게이션, 광고 등)
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form", "iframe"]):
            tag.decompose()

        # 2. 제목 추출
        title = ""
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
        h1 = soup.find("h1")
        if h1 and h1.get_text(strip=True):
            title = h1.get_text(strip=True)
        if not title:
            title = "web_document"

        # 3. 본문 후보 탐색 (기사 본문 태그 우선)
        article_candidates = [
            soup.find("article"),
            soup.find("div", {"id": re.compile(r"article|content|news|post|view", re.I)}),
            soup.find("div", {"class": re.compile(r"article|content|post-body|entry-content|news-view", re.I)}),
            soup.find("main")
        ]

        main_element = None
        for cand in article_candidates:
            if cand and len(cand.get_text(strip=True)) > 200:
                main_element = cand
                break

        if not main_element:
            main_element = soup.body if soup.body else soup

        # 4. 문단 추출
        paragraphs = []
        for p in main_element.find_all(["p", "div", "blockquote"]):
            text = p.get_text(separator=" ", strip=True)
            # 너무 짧거나 광고 문구 같은 것 제외
            if len(text) > 25 and text not in paragraphs:
                paragraphs.append(text)

        body_text = "\n\n".join(paragraphs) if paragraphs else main_element.get_text(separator="\n\n", strip=True)

        filename = f"{clean_filename(title)}.md"
        filepath = os.path.join(output_dir, filename)

        md_content = f"""# {title}

- **출처 URL**: {url}
- **수집 일시**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

---

## 📄 본문 내용

{body_text}
"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(md_content)

        return {
            "ok": True,
            "type": "web_article",
            "title": title,
            "filepath": filepath,
            "length": len(body_text),
            "preview": body_text[:300] + "..." if len(body_text) > 300 else body_text
        }

    except Exception as e:
        return {"ok": False, "error": f"웹 자료 스크랩 중 오류 발생: {str(e)}"}

def collect(url_or_input: str, output_dir: str = "output") -> dict:
    """입력 URL을 자동으로 판별하여 적절한 스크래퍼 실행"""
    url = url_or_input.strip()
    if "youtube.com" in url or "youtu.be" in url:
        return scrape_youtube(url, output_dir=output_dir)
    elif url.startswith("http://") or url.startswith("https://"):
        return scrape_web_article(url, output_dir=output_dir)
    else:
        return {"ok": False, "error": "올바른 http/https URL을 입력해 주세요."}
