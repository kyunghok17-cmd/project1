#!/usr/bin/env python3
"""
日本向け世代別トレンドデータ収集スクリプト
GitHub Actionsで毎日実行し、Cloudflare KVに保存
"""

import os
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime, timedelta
import ssl
import re

# 環境変数から設定を取得
CF_API_TOKEN = os.environ.get('CF_API_TOKEN') or "HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U"
CF_ACCOUNT_ID = os.environ.get('CF_ACCOUNT_ID') or "dddb47cb848a3a6100f19fdcd6811212"
CF_KV_NAMESPACE_ID = os.environ.get('CF_KV_NAMESPACE_ID') or "f5c396bf00af493abad3568261143511"

# SSL証明書検証をスキップ
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 日本向けキーワード定義（5世代、各世代30-50キーワード）
KEYWORDS = {
    'genz': [
        # SNS・動画 (12)
        'TikTok', 'YouTube Shorts', 'VTuber', 'にじさんじ', 'ホロライブ', 'Discord',
        'Instagram', 'BeReal', 'Threads', 'ライブ配信', '切り抜き動画', 'ストリーマー',
        # ゲーム (12)
        '原神', 'ブルーアーカイブ', 'Valorant', 'Apex Legends', 'スプラトゥーン3', 'eスポーツ',
        'ポケモン', 'ゼルダの伝説', 'FF16', 'ストリートファイター6', 'スターレイル', 'モンスト',
        # 音楽・エンタメ (10)
        'YOASOBI', 'Ado', 'Spotify', '推し活', 'Netflix', 'アニメ映画',
        '米津玄師', 'ボカロ', '声優', 'フェス',
        # ショッピング (6)
        'メルカリ', 'PayPay', 'SHEIN', 'ユニクロ', 'GU', 'Qoo10',
        # キャリア・学び (6)
        'ChatGPT', 'AI', '就活', 'プログラミング学習', 'インターン', '資格',
        # ライフスタイル (4)
        'MBTI', 'タイパ', 'LINE', 'カフェ巡り'
    ],
    'millennial': [
        # 資産形成 (10)
        'NISA', 'iDeCo', '投資信託', 'FIRE', '株式投資', '仮想通貨', 'S&P500', 'オルカン', '高配当株', '積立投資',
        # キャリア (8)
        '転職', '副業', 'リモートワーク', 'フリーランス', 'リスキリング', 'MBA', 'キャリアアップ', 'スキルアップ',
        # 住宅・生活 (8)
        'マンション購入', '住宅ローン', 'ふるさと納税', 'コストコ', 'IKEA', 'ポイ活', '家計管理', '節約',
        # 育児 (8)
        '保育園', '育児休暇', '子育て支援', '幼児教育', '習い事', 'ワンオペ育児', 'ベビー用品', 'マタニティ',
        # 健康 (6)
        'ジム', 'ダイエット', 'メンタルヘルス', 'スキンケア', 'ピラティス', '睡眠改善',
        # エンタメ (5)
        'Netflix', 'Amazon Prime', 'Disney+', 'サブスク', 'ポッドキャスト'
    ],
    'genx': [
        # 教育 (8)
        '中学受験', '大学受験', '塾', '予備校', '教育費', '学資保険', '進学', '奨学金',
        # 健康 (8)
        '人間ドック', 'がん検診', '更年期', '高血圧', '健康診断', '生活習慣病', 'メタボ', '糖尿病予防',
        # 介護 (8)
        '親の介護', '介護保険', '介護施設', 'デイサービス', '介護離職', 'ケアマネジャー', '訪問介護', '介護休暇',
        # キャリア・資産 (6)
        '早期退職', '役職定年', '退職金運用', '老後資金', '相続対策', '年金'
    ],
    'boomer': [
        # 年金・退職 (8)
        '年金受給', '退職金', '定年退職', '再雇用', '厚生年金', '国民年金', '年金繰り下げ', 'シニア就職',
        # 健康 (8)
        '高血圧', '糖尿病', '認知症予防', 'ウォーキング', '骨密度', '健康診断', '血圧', 'コレステロール',
        # 終活 (6)
        '終活', '遺言書', '相続', 'エンディングノート', '墓', '葬儀',
        # 生活・デジタル (6)
        '旅行', '趣味', '孫', 'マイナンバー', 'キャッシュレス', 'LINE使い方'
    ],
    'senior': [
        # 介護 (10)
        '介護認定', 'デイサービス', '訪問介護', '介護保険', '要介護', 'ケアプラン', 'ヘルパー', '福祉用具', 'ショートステイ', '介護サービス',
        # 施設 (6)
        '特別養護老人ホーム', '有料老人ホーム', 'グループホーム', 'サ高住', '老人ホーム', '介護付きマンション',
        # 医療 (6)
        '後期高齢者医療', '認知症', 'リハビリ', '訪問診療', '白内障手術', '骨粗しょう症',
        # 終末期 (4)
        '看取り', 'ホスピス', '緩和ケア', '延命治療'
    ]
}

# カテゴリ分類
def categorize_keyword(keyword):
    categories = {
        'SNS・動画': ['TikTok', 'YouTube', 'Shorts', 'BeReal', 'Instagram', '配信', '切り抜き', 'VTuber', 'ライブ', 'Threads', 'ストリーマー', 'にじさんじ', 'ホロライブ', 'Discord'],
        'ゲーム': ['原神', 'ブルアカ', 'ブルーアーカイブ', 'Valorant', 'Apex', 'ポケモン', 'スプラ', 'ゼルダ', 'FF', 'eスポーツ', 'モンスト', 'スターレイル', 'ストリートファイター'],
        '音楽・エンタメ': ['YOASOBI', 'Ado', 'ボカロ', 'Spotify', '音楽', '声優', 'アニメ', 'Netflix', '映画', '米津', '推し活', 'フェス', 'ライブ', 'Amazon Prime', 'Disney'],
        'ショッピング・決済': ['メルカリ', 'PayPay', '通販', 'フリマ', 'Amazon', '楽天', 'コストコ', 'SHEIN', 'ユニクロ', 'GU', 'IKEA', 'Qoo10', 'ポイ活'],
        'キャリア・学び': ['転職', '副業', 'リモート', 'フリーランス', '就活', 'インターン', 'プログラミング', 'AI', 'ChatGPT', '資格', 'MBA', 'リスキリング', 'キャリア', 'スキル'],
        '資産・投資': ['NISA', 'iDeCo', '投資', '株', '退職金', '年金', '資産', '相続', 'FIRE', 'S&P500', 'オルカン', '高配当', '積立'],
        '住宅': ['マンション', '住宅ローン', 'リフォーム', '住み替え', '固定資産', '持ち家'],
        '健康・医療': ['人間ドック', 'がん', '検診', '更年期', '老眼', '高血圧', '糖尿病', '入院', '手術', '白内障', 'ジム', 'ダイエット', 'メンタル', 'スキンケア', 'ピラティス', '睡眠', 'ウォーキング', '骨密度', 'メタボ', 'コレステロール', '血圧', 'リハビリ'],
        '育児・家族': ['保育園', '育児', 'ワンオペ', '子育て', '孫', '習い事', 'ベビー', 'マタニティ', '幼児教育'],
        '介護': ['介護', 'デイサービス', '訪問', 'ケアマネ', '老人ホーム', '特養', 'グループホーム', '認知症', 'ヘルパー', '福祉用具', 'ショートステイ', 'サ高住', '要介護', 'ケアプラン'],
        '終活': ['終活', '遺言', 'エンディング', '葬儀', '墓', '看取り', 'ホスピス', '緩和ケア', '延命'],
        'ライフスタイル': ['MBTI', 'タイパ', 'LINE', 'カフェ', '旅行', '趣味', 'マイナンバー', 'キャッシュレス', 'サブスク', 'ポッドキャスト'],
        '教育': ['中学受験', '大学受験', '塾', '予備校', '教育費', '学資保険', '進学', '奨学金']
    }

    for cat, keywords_list in categories.items():
        if any(k.lower() in keyword.lower() or keyword.lower() in k.lower() for k in keywords_list):
            return cat
    return 'その他'


def fetch_url(url, headers=None, timeout=30):
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  [WARN] Fetch failed: {url[:50]}... - {e}")
        return None


def fetch_news(keyword):
    """Google Newsから記事数を取得（12週間分）"""
    total = 0
    recent = 0
    now = datetime.now()

    for week in range(12):
        end_date = now - timedelta(days=week * 7)
        start_date = end_date - timedelta(days=7)
        after_str = start_date.strftime('%Y-%m-%d')
        before_str = end_date.strftime('%Y-%m-%d')

        query = f"{keyword} after:{after_str} before:{before_str}"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"

        text = fetch_url(url)
        if not text:
            continue

        week_count = len(re.findall(r'<item>', text))
        total += week_count
        if week == 0:
            recent = week_count

        time.sleep(0.2)

    return {'count': total, 'recent': recent}


def fetch_youtube(keyword):
    """YouTube検索結果数と再生回数を取得"""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}&gl=JP"
    text = fetch_url(url)
    if not text:
        return {'count': 0, 'views': 0}

    count = len(re.findall(r'"videoRenderer"', text))
    view_matches = re.findall(r'"viewCountText":\{"simpleText":"([\d,万億]+)', text)
    total_views = 0
    for m in view_matches[:10]:
        try:
            num_str = re.search(r'[\d,]+', m).group().replace(',', '')
            num = int(num_str)
            if '万' in m:
                num *= 10000
            if '億' in m:
                num *= 100000000
            total_views += num
        except:
            pass

    return {'count': count, 'views': total_views}


def fetch_wikipedia(keyword, days=90):
    """Wikipedia閲覧数を取得"""
    article = urllib.parse.quote(keyword.replace(' ', '_'))
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=days-1)
    start_str = start.strftime('%Y%m%d')
    end_str = end.strftime('%Y%m%d')

    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/ja.wikipedia/all-access/all-agents/{article}/daily/{start_str}/{end_str}"
    headers = {'User-Agent': 'TrendCollector/7.0 (https://github.com)'}

    text = fetch_url(url, headers)
    if not text:
        return 0

    try:
        data = json.loads(text)
        return sum(item.get('views', 0) for item in data.get('items', []))
    except:
        return 0


def analyze_keyword(keyword):
    """キーワードを分析"""
    news_data = fetch_news(keyword)
    yt_data = fetch_youtube(keyword)
    wiki = fetch_wikipedia(keyword)

    news = news_data['count']
    news_recent = news_data['recent']
    yt = yt_data['count']
    yt_views = yt_data['views']

    total_refs = news + yt + wiki + (yt_views // 1000)

    news_score = min(30, news_recent * 1.5 + news * 0.1)
    yt_score = min(30, yt * 1.5 + min(15, yt_views / 100000))
    wiki_score = min(20, wiki / 400)

    total_score = news_score + yt_score + wiki_score
    category = categorize_keyword(keyword)

    return {
        'keyword': keyword,
        'category': category,
        'score': round(total_score, 1),
        'totalRefs': total_refs,
        'news': news,
        'newsRecent': news_recent,
        'yt': yt,
        'ytViews': yt_views,
        'wiki': wiki
    }


def save_to_kv(gen, keywords_data):
    """Cloudflare KVにデータを保存"""
    key = f"gen7_data_jp_{gen}"
    value = json.dumps({
        'country': 'jp',
        'gen': gen,
        'keywords': keywords_data,
        'analyzedAt': datetime.now().isoformat(),
        'savedAt': datetime.now().isoformat()
    })

    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}',
        'Content-Type': 'application/json'
    }

    req = urllib.request.Request(url, data=value.encode('utf-8'), headers=headers, method='PUT')
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            result = json.loads(response.read().decode('utf-8'))
            return result.get('success', False)
    except Exception as e:
        print(f"  [ERROR] KV save failed: {e}")
        return False


def main():
    print("=" * 60)
    print("日本向け世代別トレンドデータ収集開始")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print("=" * 60)

    for gen, keywords in KEYWORDS.items():
        print(f"\n[{gen}] {len(keywords)}キーワード分析中...")

        results = []
        for i, kw in enumerate(keywords):
            print(f"  [{i+1}/{len(keywords)}] {kw}...", end=' ')
            try:
                result = analyze_keyword(kw)
                results.append(result)
                print(f"✓ score={result['score']}, refs={result['totalRefs']}")
            except Exception as e:
                print(f"✗ {e}")

            time.sleep(0.3)

        results.sort(key=lambda x: x['score'], reverse=True)

        print(f"\n  KVに保存中...", end=' ')
        if save_to_kv(gen, results):
            print(f"✓ {len(results)}件保存完了")
        else:
            print("✗ 保存失敗")

    print("\n" + "=" * 60)
    print("日本データ収集完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
