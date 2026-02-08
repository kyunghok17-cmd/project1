#!/usr/bin/env python3
"""
トレンドデータ収集スクリプト v2
GitHub Actionsから毎日実行され、Cloudflare KVにデータを蓄積する

必要な環境変数:
  CF_API_TOKEN: Cloudflare APIトークン
  CF_ACCOUNT_ID: CloudflareアカウントID
  CF_KV_NAMESPACE_ID: KVネームスペースID
"""

import urllib.request
import urllib.parse
import json
import os
import time
from datetime import datetime, timezone

# 環境変数から取得（GitHub Secretsで設定）
API_TOKEN = os.environ.get('CF_API_TOKEN', '')
ACCOUNT_ID = os.environ.get('CF_ACCOUNT_ID', '')
KV_NAMESPACE_ID = os.environ.get('CF_KV_NAMESPACE_ID', '')

# カテゴリ別キーワード（Worker側と同じ定義）
CATEGORIES = {
    'social': {
        'jp': ['リモートワーク', '副業', '少子化', 'SDGs', '高齢化', '介護', '地方移住'],
        'kr': ['재택근무', 'N잡러', '저출산', 'ESG', '고령화']
    },
    'tech': {
        'jp': ['生成AI', 'ChatGPT', 'Claude', 'Gemini', 'EV', '半導体', 'DX', '自動運転', 'メタバース'],
        'kr': ['생성형AI', 'ChatGPT', '전기차', '반도체', '자율주행', '메타버스']
    },
    'economy': {
        'jp': ['インフレ', '円安', '株価', 'NISA', '金利', '不動産', '人手不足', 'ビットコイン'],
        'kr': ['인플레이션', '환율', '주가', '부동산', '금리', '비트코인']
    },
    'culture': {
        'jp': ['アニメ', 'VTuber', 'TikTok', 'Netflix', 'eスポーツ', '推し活'],
        'kr': ['K-POP', '웹툰', '틱톡', 'OTT', 'e스포츠']
    }
}

COUNTRIES = ['jp', 'kr']


def log(message: str):
    """タイムスタンプ付きログ"""
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
    print(f"[{timestamp}] {message}")


def fetch_news_count(keyword: str, country: str) -> int:
    """Google News RSSから記事数を取得"""
    hl = 'ja' if country == 'jp' else 'ko'
    gl = 'JP' if country == 'jp' else 'KR'

    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(keyword)}&hl={hl}&gl={gl}&ceid={gl}:{hl}"

    try:
        req = urllib.request.Request(url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=20) as response:
            xml = response.read().decode('utf-8')
            count = xml.count('<item>')
            return count
    except Exception as e:
        log(f"    ⚠️ Error fetching '{keyword}': {e}")
        return 0


def kv_put(key: str, value: dict) -> bool:
    """Cloudflare KVに保存"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}/values/{urllib.parse.quote(key)}"

    data = json.dumps(value).encode('utf-8')

    req = urllib.request.Request(url, data=data, method='PUT')
    req.add_header('Authorization', f'Bearer {API_TOKEN}')
    req.add_header('Content-Type', 'application/json')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('success', False)
    except Exception as e:
        log(f"    ⚠️ KV PUT error for '{key}': {e}")
        return False


def kv_get(key: str) -> dict:
    """Cloudflare KVから取得"""
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/storage/kv/namespaces/{KV_NAMESPACE_ID}/values/{urllib.parse.quote(key)}"

    req = urllib.request.Request(url, method='GET')
    req.add_header('Authorization', f'Bearer {API_TOKEN}')

    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return {}


def collect_category(country: str, category: str) -> dict:
    """1カテゴリのデータを収集"""
    keywords = CATEGORIES.get(category, {}).get(country, [])
    if not keywords:
        return {}

    log(f"  📊 {category} ({len(keywords)} keywords)")

    counts = {}
    for kw in keywords:
        count = fetch_news_count(kw, country)
        counts[kw] = count
        log(f"    - {kw}: {count} articles")
        time.sleep(0.5)  # Rate limit対策

    return counts


def save_daily_data(country: str, category: str, counts: dict):
    """日次データを保存"""
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')

    # 日次データ
    daily_key = f"daily_{country}_{category}_{today}"
    daily_data = {
        'date': today,
        'country': country,
        'category': category,
        'keywords': counts,
        'collectedAt': datetime.now(timezone.utc).isoformat()
    }

    if kv_put(daily_key, daily_data):
        log(f"  ✅ Saved: {daily_key}")
    else:
        log(f"  ❌ Failed to save: {daily_key}")
        return

    # 履歴インデックス更新
    history_key = f"history_{country}_{category}"
    history = kv_get(history_key)

    if not isinstance(history, dict) or 'dates' not in history:
        history = {'dates': []}

    if today not in history['dates']:
        history['dates'].append(today)
        history['dates'] = sorted(history['dates'])[-30:]  # 最新30日分のみ

        if kv_put(history_key, history):
            log(f"  ✅ Updated history: {len(history['dates'])} days")


def main():
    """メイン処理"""
    log("=" * 60)
    log("🚀 Trends Data Collection Started")
    log("=" * 60)

    # 環境変数チェック
    if not all([API_TOKEN, ACCOUNT_ID, KV_NAMESPACE_ID]):
        log("❌ Missing environment variables:")
        log(f"   CF_API_TOKEN: {'✓' if API_TOKEN else '✗'}")
        log(f"   CF_ACCOUNT_ID: {'✓' if ACCOUNT_ID else '✗'}")
        log(f"   CF_KV_NAMESPACE_ID: {'✓' if KV_NAMESPACE_ID else '✗'}")
        exit(1)

    log(f"Account: {ACCOUNT_ID[:8]}...")
    log(f"KV Namespace: {KV_NAMESPACE_ID[:8]}...")

    total_keywords = 0
    categories = list(CATEGORIES.keys())

    for country in COUNTRIES:
        country_name = '🇯🇵 Japan' if country == 'jp' else '🇰🇷 Korea'
        log(f"\n{country_name}")
        log("-" * 40)

        for category in categories:
            counts = collect_category(country, category)
            if counts:
                save_daily_data(country, category, counts)
                total_keywords += len(counts)
            time.sleep(1)  # カテゴリ間の待機

    log("\n" + "=" * 60)
    log(f"✅ Collection completed: {total_keywords} keywords")
    log("=" * 60)


if __name__ == '__main__':
    main()
