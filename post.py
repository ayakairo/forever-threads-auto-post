#!/usr/bin/env python3
"""
フォーエバー Threads自動投稿スクリプト
投稿ストックファイルを直接読んで次の未投稿を投稿し、[x] に更新する。
（X自動投稿 career-x-auto-post と同じ構造）

- 短文: 昼・夜の枠で、未投稿を上から1本ずつ
- 長文: 本文に【1】【2】… がある投稿。週1回、LONG_WEEKDAY の夜枠だけで連投（ツリー）として出す
- DRY_RUN=1 で、投稿せずに「次に何が出るか」だけ表示する
"""

from __future__ import annotations

import os
import re
import sys
import time
import requests
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 優先順位:
# 1. 環境変数 POSTS_FILE（GitHub Actions から指定）
# 2. ローカル開発: プロジェクトルートの投稿ストック
if os.environ.get("POSTS_FILE"):
    POSTS_FILE = Path(os.environ["POSTS_FILE"])
else:
    POSTS_FILE = Path(__file__).parent.parent.parent / "in_フォーエバー/Threads/投稿ストック.md"

API_BASE = "https://graph.threads.net/v1.0"
JST = timezone(timedelta(hours=9))
MAX_CHARS = 500          # Threadsの1投稿あたりの上限
LONG_WEEKDAY = 6         # 長文を出す曜日（月=0 … 日=6）
NIGHT_START_HOUR = 17    # この時刻(JST)以降の実行を「夜枠」とみなす
DRY_RUN = os.environ.get("DRY_RUN") == "1"

HEADER_RE = re.compile(r"^- \[( |x)\] \*\*(\d+)\.(.*)$")
PART_RE = re.compile(r"^【\d+】$")


def parse_stock(text: str) -> list[dict]:
    """投稿ストックから投稿一覧を取得。本文は見出し行の次から `---` の手前まで"""
    posts = []
    current = None
    for line in text.splitlines():
        m = HEADER_RE.match(line)
        if m:
            current = {"done": m.group(1) == "x", "num": int(m.group(2)), "lines": []}
            posts.append(current)
        elif line.strip() == "---" or line.startswith("#"):
            current = None
        elif current is not None:
            current["lines"].append(line.strip())

    for p in posts:
        p["parts"] = split_parts(p.pop("lines"))
        p["long"] = len(p["parts"]) > 1
    return posts


def split_parts(lines: list[str]) -> list[str]:
    """【1】【2】… で区切って連投のパーツにする。区切りがなければ1パーツ"""
    parts, buf = [], []
    for line in lines:
        if PART_RE.match(line):
            parts.append(buf)
            buf = []
        else:
            buf.append(line)
    parts.append(buf)
    return [t for t in ("\n".join(b).strip() for b in parts) if t]


def pick_next(posts: list[dict], now: datetime) -> dict | None:
    """この枠で出す投稿を決める。長文は週1回の夜枠だけ、それ以外は短文を上から"""
    pending = [p for p in posts if not p["done"] and p["parts"]]
    is_long_slot = now.weekday() == LONG_WEEKDAY and now.hour >= NIGHT_START_HOUR
    if is_long_slot:
        for p in pending:
            if p["long"]:
                return p
    for p in pending:
        if not p["long"]:
            return p
    return None


def mark_done(posts_path: Path, num: int):
    """投稿済みとして該当行の [ ] を [x] に更新"""
    text = posts_path.read_text(encoding="utf-8")
    updated = text.replace(f"- [ ] **{num}.", f"- [x] **{num}.", 1)
    posts_path.write_text(updated, encoding="utf-8")


def api_post(path: str, token: str, data: dict) -> dict:
    res = requests.post(f"{API_BASE}/{path}", data={**data, "access_token": token}, timeout=30)
    if not res.ok:
        # トークンをログに出さないよう、レスポンス本文だけ表示する
        print(f"❌ APIエラー {res.status_code}: {res.text[:300]}")
        res.raise_for_status()
    return res.json()


def publish(text: str, token: str, reply_to_id: str | None = None) -> str:
    """1投稿を公開してpost_idを返す。reply_to_id を渡すと、その投稿への返信（連投）になる"""
    data = {"media_type": "TEXT", "text": text}
    if reply_to_id:
        data["reply_to_id"] = reply_to_id
    creation_id = api_post("me/threads", token, data)["id"]
    time.sleep(5)  # Threads API推奨: コンテナ作成後に少し待つ
    return api_post("me/threads_publish", token, {"creation_id": creation_id})["id"]


def main():
    posts = parse_stock(POSTS_FILE.read_text(encoding="utf-8"))
    now = datetime.now(JST)
    post = pick_next(posts, now)

    if post is None:
        print("✅ この枠で出せる未投稿がありません。ストックを補充してください。")
        sys.exit(0)

    too_long = [i for i, t in enumerate(post["parts"], 1) if len(t) > MAX_CHARS]
    if too_long:
        print(f"❌ #{post['num']} の {too_long} 番目が{MAX_CHARS}字を超えています。本文を直してください。")
        sys.exit(1)

    kind = f"長文・{len(post['parts'])}連投" if post["long"] else "短文"
    print(f"📝 投稿準備: #{post['num']}（{kind}）")

    if DRY_RUN:
        for i, t in enumerate(post["parts"], 1):
            print(f"--- [{i}/{len(post['parts'])}] {len(t)}字 ---\n{t}")
        print("（DRY_RUN のため投稿していません）")
        return

    token = os.environ["THREADS_ACCESS_TOKEN"]
    parent_id = None
    try:
        for i, t in enumerate(post["parts"], 1):
            parent_id = publish(t, token, reply_to_id=parent_id)
            print(f"   [{i}/{len(post['parts'])}] 公開 Post ID: {parent_id}")
            if i < len(post["parts"]):
                time.sleep(10)
    except Exception:
        if parent_id:
            # 連投の途中で止まった。先頭から二重に出さないよう投稿済みにして、続きは手動で足す
            mark_done(POSTS_FILE, post["num"])
            print(f"⚠️ #{post['num']} は連投の途中で失敗しました。続きは手動で投稿してください。")
        sys.exit(1)

    mark_done(POSTS_FILE, post["num"])
    print(f"✅ 投稿完了: #{post['num']}")


if __name__ == "__main__":
    main()
