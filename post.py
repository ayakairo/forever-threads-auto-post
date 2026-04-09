#!/usr/bin/env python3
"""
フォーエバービジネス Threads自動投稿スクリプト
posts.mdから次の投稿を取得してThreadsに投稿する
"""

import os
import re
import sys
import time
import requests
from pathlib import Path

# 環境変数からトークンを取得
ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
USER_ID = os.environ["THREADS_USER_ID"]

POSTS_FILE = Path(__file__).parent / "posts.md"
POSTED_LOG = Path(__file__).parent / "posted.log"

API_BASE = "https://graph.threads.net/v1.0"


def load_posts(filepath: Path) -> list[dict]:
    """posts.mdから投稿リストを取得"""
    content = filepath.read_text(encoding="utf-8")
    posts = []

    pattern = r"### (投稿[①-㊿\d]+(?:[（(][^)）]*[)）]?)?)\n\n(.*?)(?=\n---|\Z)"
    matches = re.finditer(pattern, content, re.DOTALL)

    for m in matches:
        title = m.group(1).strip()
        text = m.group(2).strip()
        posts.append({"title": title, "text": text})

    return posts


def load_posted_log() -> set:
    if not POSTED_LOG.exists():
        return set()
    return set(POSTED_LOG.read_text(encoding="utf-8").splitlines())


def save_posted(title: str):
    with open(POSTED_LOG, "a", encoding="utf-8") as f:
        f.write(f"{title}\n")


def get_next_post(posts, posted):
    for post in posts:
        if post["title"] not in posted:
            return post
    return None


def create_container(text: str) -> str:
    """投稿コンテナを作成してcreation_idを返す"""
    url = f"{API_BASE}/{USER_ID}/threads"
    res = requests.post(url, data={
        "media_type": "TEXT",
        "text": text,
        "access_token": ACCESS_TOKEN,
    })
    res.raise_for_status()
    return res.json()["id"]


def publish_post(creation_id: str) -> str:
    """コンテナを公開してpost_idを返す"""
    url = f"{API_BASE}/{USER_ID}/threads_publish"
    res = requests.post(url, data={
        "creation_id": creation_id,
        "access_token": ACCESS_TOKEN,
    })
    res.raise_for_status()
    return res.json()["id"]


def main():
    posts = load_posts(POSTS_FILE)
    if not posts:
        print("❌ 投稿案が見つかりませんでした")
        sys.exit(1)

    posted = load_posted_log()
    post = get_next_post(posts, posted)

    if post is None:
        print("✅ 全投稿が完了しています。新しい投稿文を追加してください。")
        sys.exit(0)

    print(f"📝 投稿準備: {post['title']}")

    creation_id = create_container(post["text"])
    time.sleep(5)  # Threads API推奨: コンテナ作成後に少し待つ
    post_id = publish_post(creation_id)

    save_posted(post["title"])
    print(f"✅ 投稿完了: {post['title']}")
    print(f"   Post ID: {post_id}")
    print(f"   {post['text'][:50]}...")


if __name__ == "__main__":
    main()
