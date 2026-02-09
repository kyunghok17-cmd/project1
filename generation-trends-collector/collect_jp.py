#!/usr/bin/env python3
"""
日本向け世代別トレンドデータ収集スクリプト
GitHub Actionsで毎日実行し、Cloudflare KVに保存

機能:
1. 過去キーワードの継承（KVから取得）
2. Google Trends急上昇ワードの自動検出
3. 世代判定によるキーワード分類
4. スコアベースの自然な新陳代謝（低スコアは脱落、高スコアは継続）
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

# 設定
MAX_KEYWORDS_PER_GEN = 50  # 各世代の最大キーワード数
MAX_INHERITED_KEYWORDS = 40  # 継承キーワードの最大数（上位40件のみ継承、下位は脱落）
MAX_NEW_TRENDS_PER_GEN = 20  # 各世代に追加する新規トレンドの最大数
HISTORY_DAYS_TO_KEEP = 30  # 保持する履歴日数

# シードキーワード（初回実行時または前回データが少ない場合に使用）
SEED_KEYWORDS = {
    'genz': ['TikTok', 'VTuber', '原神', 'Apex Legends', 'YOASOBI', 'Ado', 'ChatGPT', 'MBTI', 'メルカリ', '推し活'],
    'millennial': ['NISA', '転職', 'ふるさと納税', '住宅ローン', '育児', 'Netflix', '副業', 'iDeCo', 'コストコ', 'ピラティス'],
    'genx': ['中学受験', '介護保険', '更年期', '年金', '相続', '大学受験', '人間ドック', '教育費', '住宅ローン', '健康診断']
}

# 世代判定パターン（キーワードがどの世代に関連するかを判定）
GENERATION_PATTERNS = {
    'genz': {
        'keywords': ['TikTok', 'YouTube', 'Shorts', 'VTuber', 'にじさんじ', 'ホロライブ', 'Discord',
                     'BeReal', 'Threads', '配信', 'ストリーマー', '切り抜き',
                     '原神', 'ブルアカ', 'ブルーアーカイブ', 'Valorant', 'Apex', 'スプラ',
                     'ポケモン', 'ゼルダ', 'FF16', 'モンスト', 'スターレイル', 'eスポーツ',
                     'YOASOBI', 'Ado', '米津', 'ボカロ', '声優', '推し活', 'アニメ',
                     'メルカリ', 'PayPay', 'SHEIN', 'Qoo10',
                     'ChatGPT', 'AI', '就活', 'インターン', 'プログラミング',
                     'MBTI', 'タイパ', 'Z世代', '映え', 'バズ', 'エモい', 'ぴえん',
                     'なろう', '異世界', 'ラノベ', 'コスプレ', 'コミケ', 'ガチャ'],
        'age_range': (10, 25)
    },
    'millennial': {
        'keywords': ['NISA', 'iDeCo', '投資信託', 'FIRE', '株式投資', '仮想通貨', 'S&P500', 'オルカン',
                     '転職', '副業', 'リモートワーク', 'フリーランス', 'リスキリング', 'MBA',
                     'マンション購入', '住宅ローン', 'ふるさと納税', 'コストコ', 'IKEA', 'ポイ活',
                     '保育園', '育児', '子育て', 'ワンオペ', '習い事', 'ベビー', 'マタニティ',
                     'ジム', 'ダイエット', 'メンタルヘルス', 'ピラティス', 'Netflix', 'サブスク',
                     'ミレニアル', '30代', '共働き', 'ワークライフバランス', 'タワマン'],
        'age_range': (26, 40)
    },
    'genx': {
        'keywords': ['中学受験', '大学受験', '塾', '予備校', '教育費', '学資保険', '進学', '奨学金',
                     '人間ドック', 'がん検診', '更年期', '高血圧', '健康診断', '生活習慣病', 'メタボ',
                     '親の介護', '介護保険', '介護施設', 'デイサービス', '介護離職', 'ケアマネ',
                     '早期退職', '役職定年', '退職金運用', '老後資金', '相続対策', '年金',
                     'X世代', '40代', '50代', '住宅ローン完済', 'リフォーム'],
        'age_range': (41, 55)
    },
    'boomer': {
        'keywords': ['年金受給', '退職金', '定年退職', '再雇用', '厚生年金', '国民年金', 'シニア就職',
                     '糖尿病', '認知症予防', 'ウォーキング', '骨密度', '血圧', 'コレステロール',
                     '終活', '遺言書', '相続', 'エンディングノート', '墓', '葬儀',
                     '旅行', '趣味', '孫', 'マイナンバー', 'キャッシュレス', 'LINE使い方',
                     'ベビーブーマー', '団塊', '60代', '70代', 'シニア'],
        'age_range': (56, 70)
    },
    'senior': {
        'keywords': ['介護認定', 'デイサービス', '訪問介護', '要介護', 'ケアプラン', 'ヘルパー', '福祉用具',
                     '特別養護老人ホーム', '有料老人ホーム', 'グループホーム', 'サ高住', '老人ホーム',
                     '後期高齢者', '高齢者医療', '認知症', 'リハビリ', '訪問看護',
                     '看取り', 'ホスピス', '緩和ケア', '延命治療', '尊厳死',
                     'シニア', '80代', '90代', '高齢者', 'お年寄り'],
        'age_range': (71, 100)
    }
}

# カテゴリ分類パターン
CATEGORY_PATTERNS = {
    'SNS・動画': ['TikTok', 'YouTube', 'Shorts', 'BeReal', 'Instagram', '配信', '切り抜き', 'VTuber', 'ライブ', 'Threads', 'ストリーマー', 'にじさんじ', 'ホロライブ', 'Discord', 'X(Twitter)', 'LINE'],
    'ゲーム': ['原神', 'ブルアカ', 'ブルーアーカイブ', 'Valorant', 'Apex', 'ポケモン', 'スプラ', 'ゼルダ', 'FF', 'eスポーツ', 'モンスト', 'スターレイル', 'ストリートファイター', 'ゲーム', 'Switch', 'PS5', 'Steam'],
    '音楽・エンタメ': ['YOASOBI', 'Ado', 'ボカロ', 'Spotify', '音楽', '声優', 'アニメ', 'Netflix', '映画', '米津', '推し活', 'フェス', 'ライブ', 'Amazon Prime', 'Disney', 'ドラマ', 'コンサート'],
    'ショッピング・決済': ['メルカリ', 'PayPay', '通販', 'フリマ', 'Amazon', '楽天', 'コストコ', 'SHEIN', 'ユニクロ', 'GU', 'IKEA', 'Qoo10', 'ポイ活', 'クーポン', 'セール'],
    'キャリア・学び': ['転職', '副業', 'リモート', 'フリーランス', '就活', 'インターン', 'プログラミング', 'AI', 'ChatGPT', '資格', 'MBA', 'リスキリング', 'キャリア', 'スキル', '起業'],
    '資産・投資': ['NISA', 'iDeCo', '投資', '株', '退職金', '年金', '資産', '相続', 'FIRE', 'S&P500', 'オルカン', '高配当', '積立', '仮想通貨', 'FX'],
    '住宅': ['マンション', '住宅ローン', 'リフォーム', '住み替え', '固定資産', '持ち家', '賃貸', '引っ越し', '不動産'],
    '健康・医療': ['人間ドック', 'がん', '検診', '更年期', '老眼', '高血圧', '糖尿病', '入院', '手術', '白内障', 'ジム', 'ダイエット', 'メンタル', 'スキンケア', 'ピラティス', '睡眠', 'ウォーキング', '骨密度', 'メタボ', 'コレステロール', '血圧', 'リハビリ', '美容'],
    '育児・家族': ['保育園', '育児', 'ワンオペ', '子育て', '孫', '習い事', 'ベビー', 'マタニティ', '幼児教育', '出産', '妊娠'],
    '介護': ['介護', 'デイサービス', '訪問', 'ケアマネ', '老人ホーム', '特養', 'グループホーム', '認知症', 'ヘルパー', '福祉用具', 'ショートステイ', 'サ高住', '要介護', 'ケアプラン'],
    '終活': ['終活', '遺言', 'エンディング', '葬儀', '墓', '看取り', 'ホスピス', '緩和ケア', '延命'],
    'ライフスタイル': ['MBTI', 'タイパ', 'カフェ', '旅行', '趣味', 'マイナンバー', 'キャッシュレス', 'サブスク', 'ポッドキャスト', 'グルメ', 'レシピ', '料理'],
    '教育': ['中学受験', '大学受験', '塾', '予備校', '教育費', '学資保険', '進学', '奨学金', '偏差値', '合格']
}


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


def get_previous_keywords_from_kv(gen):
    """前回保存されたキーワードをKVから取得"""
    key = f"gen7_data_jp_{gen}"
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}'
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            keywords = data.get('keywords', [])
            print(f"  → 前回のキーワード: {len(keywords)}件")
            return keywords
    except Exception as e:
        print(f"  [INFO] 前回データなし（初回実行）: {e}")
        return []


def fetch_google_trends_jp():
    """Google Trendsから日本の急上昇ワードを取得"""
    print("\n  Google Trends (日本) から急上昇ワードを取得中...")

    trends = []

    # Google Trends RSS
    rss_urls = [
        "https://trends.google.co.jp/trending/rss?geo=JP",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=JP"
    ]

    for rss_url in rss_urls:
        try:
            text = fetch_url(rss_url, timeout=15)
            if text:
                titles = re.findall(r'<title>([^<]+)</title>', text)
                for title in titles[1:30]:
                    title = title.strip()
                    if title and len(title) > 1 and title not in trends:
                        if not title.startswith('Daily Search') and not title.startswith('Google'):
                            trends.append(title)

            time.sleep(0.5)
        except Exception as e:
            print(f"  [WARN] Google Trends取得失敗: {e}")

    # Yahoo!リアルタイム検索からも取得を試みる
    try:
        yahoo_url = "https://search.yahoo.co.jp/realtime"
        text = fetch_url(yahoo_url, timeout=15)
        if text:
            yahoo_trends = re.findall(r'<a[^>]*class="[^"]*trend[^"]*"[^>]*>([^<]+)</a>', text)
            for trend in yahoo_trends[:20]:
                trend = trend.strip()
                if trend and len(trend) > 1 and trend not in trends:
                    trends.append(trend)
    except Exception as e:
        print(f"  [WARN] Yahoo!リアルタイム取得失敗: {e}")

    print(f"  → {len(trends)}件の急上昇ワードを検出")
    return trends[:50]


def detect_generation(keyword):
    """キーワードから世代を推定"""
    keyword_lower = keyword.lower()

    scores = {}
    for gen, patterns in GENERATION_PATTERNS.items():
        score = 0
        for pattern in patterns['keywords']:
            if pattern.lower() in keyword_lower or keyword_lower in pattern.lower():
                score += 1
        scores[gen] = score

    # 最もスコアの高い世代を返す（同点の場合はgenzを優先）
    max_score = max(scores.values())
    if max_score > 0:
        for gen in ['genz', 'millennial', 'genx', 'boomer', 'senior']:
            if scores[gen] == max_score:
                return gen

    # マッチしない場合はgenzをデフォルトに（若年層のトレンドが多いため）
    return 'genz'


def classify_trends_by_generation(trends, existing_keywords_set):
    """トレンドワードを世代別に分類"""
    classified = {gen: [] for gen in GENERATION_PATTERNS.keys()}

    for trend in trends:
        # 既存キーワードと重複していたらスキップ
        if trend.lower() in existing_keywords_set:
            continue

        # 世代を判定
        gen = detect_generation(trend)
        if gen and len(classified[gen]) < MAX_NEW_TRENDS_PER_GEN:
            classified[gen].append(trend)

    return classified


def categorize_keyword(keyword):
    """キーワードをカテゴリに分類"""
    for cat, patterns in CATEGORY_PATTERNS.items():
        if any(p.lower() in keyword.lower() or keyword.lower() in p.lower() for p in patterns):
            return cat
    return 'その他'


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
    headers = {'User-Agent': 'TrendCollector/8.0 (https://github.com)'}

    text = fetch_url(url, headers)
    if not text:
        return 0

    try:
        data = json.loads(text)
        items = data.get('items', [])
        return sum(item.get('views', 0) for item in items)
    except:
        return 0


def analyze_keyword(keyword):
    """キーワードの各種メトリクスを取得してスコア計算"""
    news = fetch_news(keyword)
    yt = fetch_youtube(keyword)
    wiki = fetch_wikipedia(keyword)

    # スコア計算（重み付け）
    news_score = min(news['count'] * 0.5, 30)
    recent_bonus = min(news['recent'] * 2, 20)
    yt_score = min(yt['count'] * 0.8, 25)
    wiki_score = min(wiki / 10000, 25)

    total_score = round(news_score + recent_bonus + yt_score + wiki_score, 1)

    return {
        'keyword': keyword,
        'category': categorize_keyword(keyword),
        'news': news['count'],
        'newsRecent': news['recent'],
        'yt': yt['count'],
        'ytViews': yt['views'],
        'wiki': wiki,
        'score': total_score,
        'totalRefs': news['count'] + yt['count'] + wiki,
        'analyzedAt': datetime.now().isoformat()
    }


def save_to_kv(gen, results):
    """結果をCloudflare KVに保存"""
    key = f"gen7_data_jp_{gen}"

    # カテゴリでグループ化
    categories = {}
    for r in results:
        cat = r.get('category', 'その他')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    # 各カテゴリをスコア順にソート
    for cat in categories:
        categories[cat].sort(key=lambda x: x['score'], reverse=True)

    value = json.dumps({
        'generation': gen,
        'country': 'jp',
        'period': '3か月',
        'analyzedAt': datetime.now().isoformat(),
        'dataSource': 'auto-trends + inherited',
        'keywords': results,
        'categories': [{'name': k, 'keywords': v} for k, v in categories.items()],
        'totalRefs': sum(r.get('totalRefs', 0) for r in results),
        'avgScore': round(sum(r.get('score', 0) for r in results) / len(results), 1) if results else 0
    }, ensure_ascii=False)

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


def get_score_history(gen):
    """スコア履歴を取得"""
    key = f"gen7_history_jp_{gen}"
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {'Authorization': f'Bearer {CF_API_TOKEN}'}

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            return json.loads(response.read().decode('utf-8'))
    except:
        return {'history': {}, 'updatedAt': None}


def save_score_history(gen, history_data):
    """スコア履歴を保存"""
    key = f"gen7_history_jp_{gen}"

    # 古いデータを削除
    cutoff_date = (datetime.now() - timedelta(days=HISTORY_DAYS_TO_KEEP)).strftime('%Y-%m-%d')
    for kw in list(history_data.get('history', {}).keys()):
        dates = history_data['history'][kw]
        history_data['history'][kw] = {d: v for d, v in dates.items() if d >= cutoff_date}
        if not history_data['history'][kw]:
            del history_data['history'][kw]

    history_data['updatedAt'] = datetime.now().isoformat()
    value = json.dumps(history_data, ensure_ascii=False)

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
        print(f"  [ERROR] History save failed: {e}")
        return False


def main():
    print("=" * 60)
    print("日本向け世代別トレンドデータ収集開始（自動トレンドモード）")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: Google Trendsから新規トレンドを取得
    print("\n" + "-" * 40)
    print("Phase 1: 新規トレンド取得")
    print("-" * 40)

    new_trends = fetch_google_trends_jp()

    # Step 2: 各世代のキーワードを処理
    print("\n" + "-" * 40)
    print("Phase 2: 世代別キーワード処理")
    print("-" * 40)

    # 対象世代（boomer, seniorは除外）
    target_generations = ['genz', 'millennial', 'genx']

    for gen in target_generations:
        print(f"\n{'='*50}")
        print(f"[{gen.upper()}] 処理開始")
        print(f"{'='*50}")

        # 前回のキーワードを取得
        previous_keywords = get_previous_keywords_from_kv(gen)
        previous_kw_names = set(k.get('keyword', '').lower() for k in previous_keywords)

        # スコア履歴を取得
        history_data = get_score_history(gen)
        today = datetime.now().strftime('%Y-%m-%d')

        # 新規トレンドを世代別に分類
        classified_trends = classify_trends_by_generation(new_trends, previous_kw_names)
        gen_new_trends = classified_trends.get(gen, [])

        print(f"  前回キーワード: {len(previous_keywords)}件")
        print(f"  新規トレンド候補: {len(gen_new_trends)}件")

        # 分析対象キーワードを構築
        # 1. 前回のキーワード（継承）
        # 2. 新規トレンド（追加）
        keywords_to_analyze = []

        # 前回のキーワードをスコア順にソートして上位のみ継承
        inherited_count = 0
        dropped_count = 0

        # スコア順にソート（高い順）
        sorted_prev_keywords = sorted(previous_keywords, key=lambda x: x.get('score', 0), reverse=True)

        for prev_kw in sorted_prev_keywords:
            kw_name = prev_kw.get('keyword', '')
            prev_score = prev_kw.get('score', 0)

            # 空のキーワードはスキップ
            if not kw_name or not kw_name.strip():
                continue

            # 上位MAX_INHERITED_KEYWORDS件のみ継承（下位は自動脱落）
            if inherited_count >= MAX_INHERITED_KEYWORDS:
                dropped_count += 1
                print(f"  [DROP] {kw_name} (ランキング{inherited_count + dropped_count}位, score={prev_score})")
                continue

            keywords_to_analyze.append({
                'keyword': kw_name,
                'isInherited': True,
                'prevScore': prev_score
            })
            inherited_count += 1

        print(f"  継承: {inherited_count}件 (上位{MAX_INHERITED_KEYWORDS}位まで), 脱落: {dropped_count}件")

        # 新規トレンドを追加（最大数まで）
        remaining_slots = MAX_KEYWORDS_PER_GEN - len(keywords_to_analyze)
        new_trends_to_add = gen_new_trends[:remaining_slots]

        for trend in new_trends_to_add:
            keywords_to_analyze.append({
                'keyword': trend,
                'isNew': True
            })

        print(f"  新規追加: {len(new_trends_to_add)}件")

        # 初回実行時またはキーワードが少なすぎる場合、シードキーワードを追加
        seed_count = 0
        if len(keywords_to_analyze) < 10 and gen in SEED_KEYWORDS:
            existing_kws = set(k['keyword'].lower() for k in keywords_to_analyze)
            for seed in SEED_KEYWORDS[gen]:
                if seed.lower() not in existing_kws and len(keywords_to_analyze) < MAX_KEYWORDS_PER_GEN:
                    keywords_to_analyze.append({
                        'keyword': seed,
                        'isNew': True,
                        'isSeed': True
                    })
                    seed_count += 1
            print(f"  シード追加: {seed_count}件")

        print(f"  合計分析対象: {len(keywords_to_analyze)}件")

        # キーワード分析
        print(f"\n  分析実行中...")
        results = []

        for i, kw_data in enumerate(keywords_to_analyze):
            kw = kw_data['keyword']
            is_new = kw_data.get('isNew', False)
            prefix = "🆕" if is_new else "📌"
            print(f"  [{i+1}/{len(keywords_to_analyze)}] {prefix} {kw}...", end=' ')

            try:
                result = analyze_keyword(kw)
                result['isNew'] = is_new
                result['isTrending'] = is_new

                # スコア変動を計算
                if 'prevScore' in kw_data:
                    change = round(result['score'] - kw_data['prevScore'], 1)
                    result['scoreChange'] = change
                    result['prevScore'] = kw_data['prevScore']

                # 履歴に追加
                if kw not in history_data.get('history', {}):
                    if 'history' not in history_data:
                        history_data['history'] = {}
                    history_data['history'][kw] = {}
                history_data['history'][kw][today] = result['score']

                results.append(result)

                # 変動表示
                change_str = ""
                if 'scoreChange' in result and result['scoreChange'] != 0:
                    arrow = "↑" if result['scoreChange'] > 0 else "↓"
                    change_str = f" ({arrow}{abs(result['scoreChange'])})"

                print(f"✓ score={result['score']}{change_str}")
            except Exception as e:
                print(f"✗ {e}")

            time.sleep(0.3)

        # スコア順にソート
        results.sort(key=lambda x: x['score'], reverse=True)

        # 最大数に制限
        if len(results) > MAX_KEYWORDS_PER_GEN:
            results = results[:MAX_KEYWORDS_PER_GEN]

        # KVに保存
        if not results:
            print(f"\n  [WARN] 分析結果が0件のためスキップ")
            continue

        print(f"\n  KVに保存中...", end=' ')
        if save_to_kv(gen, results):
            new_count = len([r for r in results if r.get('isNew')])
            print(f"✓ {len(results)}件保存（うち新規{new_count}件）")
        else:
            print("✗ 保存失敗")

        # 履歴保存
        print(f"  履歴を保存中...", end=' ')
        if save_score_history(gen, history_data):
            print("✓")
        else:
            print("✗ 保存失敗")

    print("\n" + "=" * 60)
    print("日本データ収集完了（自動トレンドモード）")
    print("=" * 60)


if __name__ == '__main__':
    main()
