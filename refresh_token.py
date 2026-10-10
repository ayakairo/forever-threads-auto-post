#!/usr/bin/env python3
"""
Threadsアクセストークン更新スクリプト
トークンは60日で期限切れになるため、月1回自動更新する。
新しいトークンは画面に出さず、TOKEN_OUT のファイルにだけ書く（ワークフローがSecretsへ登録する）
"""

import os
import sys
import requests
from pathlib import Path

ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
TOKEN_OUT = Path(os.environ["TOKEN_OUT"])
API_URL = "https://graph.threads.net/refresh_access_token"


def refresh():
    res = requests.get(API_URL, params={
        "grant_type": "th_refresh_token",
        "access_token": ACCESS_TOKEN,
    }, timeout=30)
    if not res.ok:
        print(f"❌ トークン更新に失敗 {res.status_code}: {res.text[:300]}")
        sys.exit(1)
    data = res.json()
    TOKEN_OUT.write_text(data["access_token"], encoding="utf-8")
    print(f"✅ トークン更新完了（有効期限: あと {data.get('expires_in', 0) // 86400} 日）")


if __name__ == "__main__":
    refresh()
