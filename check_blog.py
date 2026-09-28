"""네이버 블로그 새 글을 확인해서 텔레그램으로 알림을 보냅니다."""
import json
import os
import re
import sys
import urllib.parse
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET

BLOG_ID = os.environ.get("BLOG_ID", "ranto28")
RSS_URL = f"https://rss.blog.naver.com/{BLOG_ID}.xml"
STATE_FILE = "last_seen.json"
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def fetch_posts():
    req = urllib.request.Request(RSS_URL, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"[RSS 읽기 실패] HTTP {e.code}: {RSS_URL}") from None
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        raise RuntimeError(f"[RSS 해석 실패] 응답 앞부분: {raw[:200]!r}") from None
    posts = []
    for item in root.iter("item"):
        link = (item.findtext("link") or "").strip()
        m = re.search(r"/(\d{9,})", link)
        if not m:
            continue
        log_no = m.group(1)
        posts.append({
            "id": log_no,
            "title": (item.findtext("title") or "(제목 없음)").strip(),
            # 모바일 주소: 폰에서 누르면 바로 글이 열림
            "url": f"https://m.blog.naver.com/{BLOG_ID}/{log_no}",
        })
    return posts  # 최신 글이 앞쪽


def send(text):
    data = urllib.parse.urlencode({"chat_id": CHAT_ID, "text": text}).encode()
    try:
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=data, timeout=30
        ).read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        raise RuntimeError(f"[텔레그램 전송 실패] HTTP {e.code}: {body}") from None


def main():
    if not TOKEN:
        raise RuntimeError("[설정 오류] Secrets에 TELEGRAM_BOT_TOKEN이 없습니다 (이름 철자 확인).")
    if not CHAT_ID:
        raise RuntimeError("[설정 오류] Secrets에 TELEGRAM_CHAT_ID가 없습니다 (이름 철자 확인).")
    posts = fetch_posts()
    if not posts:
        print("RSS에서 글을 찾지 못했습니다.")
        return

    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            seen = set(json.load(f))
        first_run = False
    else:
        seen = set()
        first_run = True

    if first_run:
        send(f"✅ 블로그 알림 설정 완료\n최신 글: {posts[0]['title']}\n{posts[0]['url']}")
    else:
        new_posts = [p for p in posts if p["id"] not in seen]
        for p in reversed(new_posts):  # 오래된 글부터 순서대로
            send(f"📝 새 글: {p['title']}\n{p['url']}")
        print(f"새 글 {len(new_posts)}개")

    seen.update(p["id"] for p in posts)
    # 최근 100개만 보관
    keep = sorted(seen, key=int, reverse=True)[:100]
    with open(STATE_FILE, "w") as f:
        json.dump(keep, f)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"::error::{e}")
        print(f"오류: {e}", file=sys.stderr)
        sys.exit(1)
