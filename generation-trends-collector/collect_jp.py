#!/usr/bin/env python3
"""
日本向け世代別トレンドデータ収集スクリプト
GitHub Actionsで毎日実行し、Cloudflare KVに保存

機能:
1. 事前定義キーワードの分析
2. Google Trends急上昇ワードの自動検出
3. 世代判定によるキーワード分類
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

# 自動トレンド検出の設定
AUTO_TREND_ENABLED = True
MAX_AUTO_TRENDS_PER_GEN = 10  # 各世代に追加する自動トレンドの最大数

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

# 世代判定用キーワードパターン
GENERATION_PATTERNS = {
    'genz': {
        'keywords': ['TikTok', 'Discord', 'VTuber', 'ホロライブ', 'にじさんじ', 'ゲーム', '原神', 'Valorant', 'Apex',
                     'ブルアカ', 'スプラ', 'YOASOBI', 'Ado', '推し活', 'アニメ', 'メルカリ', 'SHEIN', 'Z世代',
                     'eスポーツ', 'Spotify', 'Netflix', 'インスタ', 'BeReal', 'ストリーマー', '切り抜き',
                     'ポケモン', 'ゼルダ', 'AI', 'ChatGPT', 'MBTI', 'タイパ', 'コスパ', '就活', 'インターン'],
        'age_range': (10, 27),
        'description': '1997年以降生まれ'
    },
    'millennial': {
        'keywords': ['NISA', 'iDeCo', '投資', '転職', '副業', 'リモートワーク', 'フリーランス', 'FIRE',
                     '住宅ローン', 'マンション', '保育園', '育児', '子育て', 'ワンオペ', 'キャリア',
                     'ふるさと納税', 'ポイ活', 'コストコ', 'サブスク', 'ダイエット', 'ジム', 'ピラティス',
                     '積立', 'S&P500', 'オルカン', '高配当', 'MBA', 'リスキリング', 'スキルアップ'],
        'age_range': (28, 43),
        'description': '1981-1996年生まれ'
    },
    'genx': {
        'keywords': ['中学受験', '大学受験', '塾', '予備校', '教育費', '介護', '親の介護', '人間ドック',
                     'がん検診', '更年期', '高血圧', '糖尿病', '早期退職', '役職定年', '退職金', '老後資金',
                     '相続', '年金', 'デイサービス', 'ケアマネ', '介護保険', '介護離職', '訪問介護',
                     '学資保険', '進学', '奨学金', '生活習慣病', 'メタボ'],
        'age_range': (44, 59),
        'description': '1965-1980年生まれ'
    },
    'boomer': {
        'keywords': ['年金受給', '定年退職', '再雇用', '厚生年金', '国民年金', '終活', '遺言', '相続',
                     '認知症予防', 'ウォーキング', '骨密度', 'コレステロール', '血圧', 'マイナンバー',
                     'キャッシュレス', 'LINE使い方', 'シニア', '孫', '趣味', '旅行', 'エンディングノート'],
        'age_range': (60, 74),
        'description': '1950-1964年生まれ'
    },
    'senior': {
        'keywords': ['介護認定', '要介護', '特養', '老人ホーム', 'グループホーム', 'サ高住', '訪問診療',
                     '後期高齢者', '認知症', 'リハビリ', '白内障', '骨粗しょう症', '看取り', 'ホスピス',
                     '緩和ケア', '延命治療', 'ヘルパー', '福祉用具', 'ショートステイ'],
        'age_range': (75, 100),
        'description': '1949年以前生まれ'
    }
}


def detect_generation(keyword):
    """キーワードから最も関連する世代を判定"""
    scores = {gen: 0 for gen in GENERATION_PATTERNS.keys()}
    keyword_lower = keyword.lower()

    for gen, pattern in GENERATION_PATTERNS.items():
        for kw in pattern['keywords']:
            if kw.lower() in keyword_lower or keyword_lower in kw.lower():
                scores[gen] += 2
            # 部分一致も考慮
            elif any(part in keyword_lower for part in kw.lower().split()):
                scores[gen] += 1

    # 最高スコアの世代を返す（同点の場合は若い世代を優先）
    max_score = max(scores.values())
    if max_score == 0:
        return None  # どの世代にも該当しない

    gen_order = ['genz', 'millennial', 'genx', 'boomer', 'senior']
    for gen in gen_order:
        if scores[gen] == max_score:
            return gen
    return None


def fetch_google_trends_jp():
    """Google Trendsの急上昇ワードを取得（日本）"""
    print("\n[AUTO] Google Trends急上昇ワードを取得中...")

    trends = []

    # Google Trends RSS（日本の急上昇）
    urls = [
        "https://trends.google.co.jp/trending/rss?geo=JP",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP"
    ]

    for url in urls:
        try:
            text = fetch_url(url, timeout=15)
            if not text:
                continue

            # RSSからトレンドワードを抽出
            titles = re.findall(r'<title>(?:<!\[CDATA\[)?([^<\]]+)(?:\]\]>)?</title>', text)
            for title in titles:
                title = title.strip()
                # フィルタリング
                if title and len(title) > 1 and title not in ['Daily Search Trends', 'Google トレンド', '急上昇ワード']:
                    if title not in trends:
                        trends.append(title)

            time.sleep(0.5)
        except Exception as e:
            print(f"  [WARN] Google Trends取得失敗: {e}")

    # Yahoo!リアルタイム検索からも取得を試みる
    try:
        yahoo_url = "https://search.yahoo.co.jp/realtime"
        text = fetch_url(yahoo_url, timeout=15)
        if text:
            # トレンドワードを抽出（パターンマッチング）
            yahoo_trends = re.findall(r'<a[^>]*class="[^"]*trend[^"]*"[^>]*>([^<]+)</a>', text)
            for trend in yahoo_trends[:20]:
                trend = trend.strip()
                if trend and len(trend) > 1 and trend not in trends:
                    trends.append(trend)
    except Exception as e:
        print(f"  [WARN] Yahoo!リアルタイム取得失敗: {e}")

    print(f"  → {len(trends)}件の急上昇ワードを検出")
    return trends[:50]  # 最大50件


def classify_trends_by_generation(trends, existing_keywords):
    """トレンドワードを世代別に分類"""
    classified = {gen: [] for gen in GENERATION_PATTERNS.keys()}

    # 既存キーワードのセットを作成（重複チェック用）
    all_existing = set()
    for gen_keywords in existing_keywords.values():
        all_existing.update(kw.lower() for kw in gen_keywords)

    for trend in trends:
        # 既存キーワードと重複していたらスキップ
        if trend.lower() in all_existing:
            continue

        # 世代を判定
        gen = detect_generation(trend)
        if gen and len(classified[gen]) < MAX_AUTO_TRENDS_PER_GEN:
            classified[gen].append(trend)
            print(f"  → [{gen}] {trend}")

    return classified


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


def save_auto_trends_to_kv(auto_trends_data):
    """自動検出トレンドをKVに保存"""
    key = "gen7_auto_trends_jp"
    value = json.dumps({
        'country': 'jp',
        'trends': auto_trends_data,
        'detectedAt': datetime.now().isoformat()
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
        print(f"  [ERROR] Auto trends KV save failed: {e}")
        return False


def main():
    print("=" * 60)
    print("日本向け世代別トレンドデータ収集開始")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: 自動トレンド検出
    auto_trends_by_gen = {}
    if AUTO_TREND_ENABLED:
        print("\n" + "-" * 40)
        print("Phase 1: 自動トレンド検出")
        print("-" * 40)

        # Google Trendsから急上昇ワードを取得
        trends = fetch_google_trends_jp()

        if trends:
            # 世代別に分類
            auto_trends_by_gen = classify_trends_by_generation(trends, KEYWORDS)

            # 分類結果を表示
            print("\n[AUTO] 世代別分類結果:")
            for gen, gen_trends in auto_trends_by_gen.items():
                if gen_trends:
                    print(f"  {gen}: {len(gen_trends)}件 - {', '.join(gen_trends[:5])}...")

    # Step 2: 事前定義キーワード + 自動トレンドの分析
    print("\n" + "-" * 40)
    print("Phase 2: キーワード分析")
    print("-" * 40)

    all_auto_trends_analyzed = {}

    for gen, keywords in KEYWORDS.items():
        # 自動トレンドを追加
        auto_trends = auto_trends_by_gen.get(gen, [])
        combined_keywords = list(keywords) + auto_trends

        print(f"\n[{gen}] {len(keywords)}定義 + {len(auto_trends)}自動 = {len(combined_keywords)}キーワード分析中...")

        results = []
        auto_results = []

        for i, kw in enumerate(combined_keywords):
            is_auto = i >= len(keywords)
            prefix = "[AUTO]" if is_auto else ""
            print(f"  [{i+1}/{len(combined_keywords)}] {prefix}{kw}...", end=' ')

            try:
                result = analyze_keyword(kw)
                result['isAutoDetected'] = is_auto  # 自動検出フラグを追加

                if is_auto:
                    auto_results.append(result)
                else:
                    results.append(result)

                print(f"✓ score={result['score']}, refs={result['totalRefs']}")
            except Exception as e:
                print(f"✗ {e}")

            time.sleep(0.3)

        # 事前定義キーワードをスコア順にソート
        results.sort(key=lambda x: x['score'], reverse=True)

        # 自動トレンドも保存用に記録
        if auto_results:
            auto_results.sort(key=lambda x: x['score'], reverse=True)
            all_auto_trends_analyzed[gen] = auto_results

        # KVに保存（事前定義キーワードのみ - 既存の動作を維持）
        print(f"\n  KVに保存中...", end=' ')
        if save_to_kv(gen, results):
            print(f"✓ {len(results)}件保存完了")
        else:
            print("✗ 保存失敗")

    # Step 3: 自動トレンド結果を別途保存
    if all_auto_trends_analyzed:
        print("\n" + "-" * 40)
        print("Phase 3: 自動トレンド結果保存")
        print("-" * 40)

        print("  自動検出トレンドをKVに保存中...", end=' ')
        if save_auto_trends_to_kv(all_auto_trends_analyzed):
            total_auto = sum(len(v) for v in all_auto_trends_analyzed.values())
            print(f"✓ {total_auto}件保存完了")
        else:
            print("✗ 保存失敗")

    print("\n" + "=" * 60)
    print("日本データ収集完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
