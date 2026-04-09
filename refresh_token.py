#!/usr/bin/env python3
"""
Threadsアクセストークン更新スクリプト
トークンは60日で期限切れになるため、月1回自動更新する
"""

import os
import sys
import requests

ACCESS_TOKEN = os.environ["THREADS_ACCESS_TOKEN"]
API_BASE = "https://graph.threads.net/refresh_access_token"


def refresh():
    res = requests.get(API_BASE, params={
        "grant_type": "th_refresh_token",
        "access_token": ACCESS_TOKEN,
    })
    res.raise_for_status()
    data = res.json()
    new_token = data.get("access_token")
    expires_in = data.get("expires_in")
    print(f"✅ トークン更新完了")
    print(f"   新しいトークン: {new_token[:20]}...")
    print(f"   有効期限: {expires_in // 86400} 日")
    print(f"\n⚠️  GitHubのSecretsを以下の値に更新してください:")
    print(f"   THREADS_ACCESS_TOKEN = {new_token}")


if __name__ == "__main__":
    refresh()
