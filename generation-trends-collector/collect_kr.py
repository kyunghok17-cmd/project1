#!/usr/bin/env python3
"""
韓国向け世代別トレンドデータ収集スクリプト
GitHub Actionsで毎日実行し、Cloudflare KVに保存

機能:
1. 過去キーワードの継承（KVから取得）
2. 複数ソースからの新規キーワード取得（Google Trends、Naver等）
3. 世代判定によるキーワード分類
4. スコアベースの自然な新陳代謝（ランキング下位は脱落）
5. 新規キーワードも事前スコア計算（低スコアは次回脱落）
6. ランダム探索による埋もれたキーワードの発掘
"""

import os
import json
import urllib.request
import urllib.parse
import time
from datetime import datetime, timedelta
import ssl
import re
import random

# 環境変数から設定を取得
CF_API_TOKEN = os.environ.get('CF_API_TOKEN') or "HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U"
CF_ACCOUNT_ID = os.environ.get('CF_ACCOUNT_ID') or "dddb47cb848a3a6100f19fdcd6811212"
CF_KV_NAMESPACE_ID = os.environ.get('CF_KV_NAMESPACE_ID') or "f5c396bf00af493abad3568261143511"

# SSL証明書検証をスキップ
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 設定
MAX_KEYWORDS_PER_GEN = 50  # 各世代の最大キーワード数（分析後にスコア上位50件を保存）
MAX_NEW_TRENDS_PER_GEN = 20  # 各世代に追加する新規トレンドの最大数
RANDOM_EXPLORE_COUNT = 5  # ランダム探索で試すキーワード数
HISTORY_DAYS_TO_KEEP = 30  # 保持する履歴日数

# シードキーワード（初回実行時または前回データが少ない場合に使用）
SEED_KEYWORDS = {
    'genz': ['틱톡', '유튜브', '원신', '발로란트', 'BTS', '뉴진스', 'ChatGPT', 'MBTI', '당근마켓', '아이돌'],
    'millennial': ['주식', '이직', '부동산', '육아', '넷플릭스', '부업', '재테크', '헬스', '아파트', '투자'],
    'genx': ['입시', '수능', '건강검진', '연금', '상속', '대입', '암검진', '교육비', '요양원', '당뇨']
}

# ランダム探索プール（埋もれている可能性のあるキーワード）
EXPLORE_POOL = {
    'genz': [
        # ゲーム
        '젠레스존제로', '학원아이돌마스터', '우마무스메', '프로세카', 'FGO',
        '붕괴스타레일', '명일방주', '포트나이트', '마인크래프트', '동물의숲',
        # 配信・SNS
        '이세계아이돌', '고세구', '주르르', '징버거', '우왁굳', '침착맨', '대도서관',
        '피식대학', '숏박스', '침투부',
        # 音楽・エンタメ
        '르세라핌', '스테이씨', '잇지', '엔시티', '세븐틴', '스트레이키즈',
        '아이유', '태연', '백현', '임영웅', '이무진', '아이들',
        # ファッション・トレンド
        'Y2K패션', '산리오', '포차코', '시나모롤', '테무', '알리익스프레스',
        # 学習・キャリア
        '노션', '웹디자인', '영상편집', '캔바', '토익', '파이썬', '개발자'
    ],
    'millennial': [
        # 投資・資産
        'ISA', 'IRP', 'S&P500', 'ETF', '배당주', '미국주식',
        '토스증권', '카카오증권', 'KB증권', '삼성증권',
        # 副業・キャリア
        '리셀', '블로그수익', '유튜브수익', '크몽', '클래스101',
        # 生活・家族
        '식기세척기', '건조기', '로봇청소기', '에어프라이어', '시간절약',
        '웅진씽크빅', '눈높이', '밀크티', '엘리하이',
        # 健康・美容
        '애니타임', '스포애니', '짐박스', '홈트', '간헐적단식',
        '오토파지', '프로틴', '피부과', '레이저', '보톡스'
    ],
    'genx': [
        # 教育
        '대성마이맥', '메가스터디', '이투스', 'EBS', '수시', '정시',
        '스카이', '인서울', '의대입시', '자사고',
        # 健康・医療
        'PET검사', 'MRI', '위내시경', '대장내시경', '전립선암', '유방암검진',
        '녹내장', '백내장수술', '노안수술', '라식', '라섹',
        # 資産・相続
        '상속세', '증여세', '가족신탁', '후견인', '부동산상속',
        '종신보험', '연금보험', '실비보험',
        # 介護
        '장기요양등급', '지역포괄케어', '방문간호', '주야간보호'
    ]
}

# 世代判定パターン（韓国版）
GENERATION_PATTERNS = {
    'genz': {
        'keywords': ['틱톡', '유튜브', '쇼츠', '버튜버', '인스타', '디스코드', '스레드',
                     '트위치', '아프리카TV', '치지직', '라이브',
                     '원신', '블루아카이브', '발로란트', 'LoL', '리그오브레전드', 'e스포츠',
                     '포켓몬', '젤다', '스플래툰', '메이플스토리', '오버워치',
                     'BTS', '아이브', '에스파', '뉴진스', 'K-POP', '아이돌', '덕질', '최애',
                     '당근마켓', '카카오페이', '쿠팡', '무신사',
                     'ChatGPT', 'AI', '취준', '자소서', '코딩',
                     'MBTI', 'Z세대', '갓생', '플렉스', 'TMI', '인싸'],
        'age_range': (10, 25)
    },
    'millennial': {
        'keywords': ['주식', '코인', '부동산', '재테크', '투자', 'ETF', '적금',
                     '이직', '퇴사', '재택근무', '프리랜서', '부업', 'N잡러',
                     '아파트', '전세', '월세', '청약', '대출', '영끌',
                     '육아', '어린이집', '출산', '워라밸', '맞벌이',
                     '헬스', '다이어트', '필라테스', '넷플릭스', '구독',
                     '밀레니얼', '30대', 'MZ세대', '카페', '브런치'],
        'age_range': (26, 40)
    },
    'genx': {
        'keywords': ['입시', '대입', '수능', '학원', '과외', '교육비', '학자금',
                     '건강검진', '암검진', '갱년기', '고혈압', '당뇨', '성인병',
                     '부모님 돌봄', '요양원', '간병', '치매',
                     '퇴직', '노후준비', '연금', '상속', '은퇴',
                     'X세대', '40대', '50대', '중년', '베이비부머'],
        'age_range': (41, 55)
    },
    'boomer': {
        'keywords': ['국민연금', '퇴직금', '정년', '재취업', '시니어',
                     '당뇨병', '치매예방', '걷기', '혈압', '콜레스테롤',
                     '유언장', '상속', '장례', '묘지',
                     '여행', '취미', '손주', '실버', '노인'],
        'age_range': (56, 70)
    },
    'senior': {
        'keywords': ['요양등급', '주간보호', '방문요양', '요양보험', '돌봄',
                     '요양원', '실버타운', '노인정', '경로당',
                     '노인의료', '치매', '재활', '호스피스', '임종',
                     '고령자', '80대', '90대', '어르신'],
        'age_range': (71, 100)
    }
}

# カテゴリ分類パターン（韓国版）
CATEGORY_PATTERNS = {
    'SNS・動画': ['틱톡', '유튜브', '쇼츠', '인스타', '라이브', '버튜버', '트위치', '아프리카', '치지직', '디스코드', '스레드', '카카오톡', 'X(트위터)'],
    '게임': ['원신', '블루아카이브', '발로란트', 'LoL', '리그오브레전드', '포켓몬', '젤다', 'e스포츠', '메이플', '오버워치', '게임', 'PC방', '스팀'],
    '음악・엔터': ['BTS', '아이브', '에스파', '뉴진스', 'K-POP', '아이돌', '덕질', '콘서트', '팬미팅', '드라마', '영화', '넷플릭스', '예능'],
    '쇼핑・결제': ['당근마켓', '쿠팡', '무신사', '카카오페이', '네이버페이', '편의점', '할인', '세일', '포인트'],
    '커리어・학습': ['이직', '퇴사', '재택', '프리랜서', '취준', '자소서', '코딩', 'AI', 'ChatGPT', '자격증', '공무원', '스펙'],
    '재테크・투자': ['주식', '코인', '부동산', 'ETF', '적금', '청약', '대출', '투자', '재테크', '연금', '상속'],
    '부동산': ['아파트', '전세', '월세', '청약', '분양', '재개발', '이사'],
    '건강・의료': ['건강검진', '암검진', '갱년기', '고혈압', '당뇨', '헬스', '다이어트', '필라테스', '정신건강', '피부', '치매', '재활'],
    '육아・가족': ['육아', '어린이집', '출산', '맞벌이', '손주', '결혼', '임신'],
    '돌봄': ['요양원', '요양등급', '주간보호', '방문요양', '간병', '치매', '돌봄', '노인정'],
    '종활': ['유언장', '상속', '장례', '묘지', '호스피스', '임종'],
    '라이프': ['MBTI', '카페', '맛집', '여행', '취미', '반려동물', '인테리어'],
    '교육': ['입시', '대입', '수능', '학원', '과외', '교육비', '유학', '영어']
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
    key = f"gen7_data_kr_{gen}"
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


def fetch_google_trends_kr():
    """Google Trendsから韓国の急上昇ワードを取得"""
    print("\n  [1/3] Google Trends (韓国) から急上昇ワードを取得中...")

    trends = []

    # Google Trends RSS
    rss_urls = [
        "https://trends.google.co.kr/trending/rss?geo=KR",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
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
            print(f"    [WARN] Google Trends取得失敗: {e}")

    print(f"    → {len(trends)}件")
    return trends


def fetch_naver_trends():
    """Naverからトレンドキーワードを取得"""
    print("  [2/3] Naverからトレンドを取得中...")

    trends = []

    try:
        naver_url = "https://www.naver.com"
        text = fetch_url(naver_url, timeout=15)
        if text:
            # 複数のパターンで抽出を試みる
            patterns = [
                r'data-clk="[^"]*">([가-힣a-zA-Z0-9\s]+)</a>',
                r'"keyword":"([^"]+)"',
                r'class="[^"]*keyword[^"]*"[^>]*>([^<]+)<'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for trend in matches[:20]:
                    trend = trend.strip()
                    if trend and len(trend) > 1 and trend not in trends:
                        trends.append(trend)
    except Exception as e:
        print(f"    [WARN] Naver取得失敗: {e}")

    print(f"    → {len(trends)}件")
    return trends


def fetch_daum_trends():
    """Daumからトレンドキーワードを取得"""
    print("  [3/3] Daumからトレンドを取得中...")

    keywords = []

    try:
        daum_url = "https://www.daum.net"
        text = fetch_url(daum_url, timeout=15)
        if text:
            # 検索ランキングを抽出
            patterns = [
                r'<a[^>]*class="[^"]*rank[^"]*"[^>]*>([^<]+)</a>',
                r'"issueKeyword":"([^"]+)"'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for kw in matches[:15]:
                    kw = kw.strip()
                    if kw and len(kw) > 1 and kw not in keywords:
                        keywords.append(kw)
    except Exception as e:
        print(f"    [WARN] Daum取得失敗: {e}")

    print(f"    → {len(keywords)}件")
    return keywords


def fetch_all_trend_sources():
    """全てのトレンドソースからキーワードを収集"""
    all_trends = []
    seen = set()

    # 各ソースから取得
    sources = [
        fetch_google_trends_kr(),
        fetch_naver_trends(),
        fetch_daum_trends()
    ]

    for trends in sources:
        for trend in trends:
            trend_lower = trend.lower()
            if trend_lower not in seen:
                seen.add(trend_lower)
                all_trends.append(trend)

    print(f"\n  合計: {len(all_trends)}件の新規トレンド候補")
    return all_trends


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

    # 最もスコアの高い世代を返す
    max_score = max(scores.values())
    if max_score > 0:
        for gen in ['genz', 'millennial', 'genx', 'boomer', 'senior']:
            if scores[gen] == max_score:
                return gen

    # マッチしない場合はgenzをデフォルトに
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
    return '기타'


def fetch_news(keyword):
    """Google Newsから記事数を取得（韓国版、12週間分）"""
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
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

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
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}&gl=KR"
    text = fetch_url(url)
    if not text:
        return {'count': 0, 'views': 0}

    count = len(re.findall(r'"videoRenderer"', text))
    view_matches = re.findall(r'"viewCountText":\{"simpleText":"([\d,만억]+)', text)
    total_views = 0
    for m in view_matches[:10]:
        try:
            num_str = re.search(r'[\d,]+', m).group().replace(',', '')
            num = int(num_str)
            if '만' in m:
                num *= 10000
            if '억' in m:
                num *= 100000000
            total_views += num
        except:
            pass

    return {'count': count, 'views': total_views}


def fetch_wikipedia(keyword, days=90):
    """Wikipedia閲覧数を取得（韓国語版）"""
    article = urllib.parse.quote(keyword.replace(' ', '_'))
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=days-1)
    start_str = start.strftime('%Y%m%d')
    end_str = end.strftime('%Y%m%d')

    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/ko.wikipedia/all-access/all-agents/{article}/daily/{start_str}/{end_str}"
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


def quick_score_check(keyword):
    """キーワードの簡易スコアチェック（高速版）"""
    # Google Newsの直近1週間のみチェック
    now = datetime.now()
    end_date = now
    start_date = end_date - timedelta(days=7)
    after_str = start_date.strftime('%Y-%m-%d')
    before_str = end_date.strftime('%Y-%m-%d')

    query = f"{keyword} after:{after_str} before:{before_str}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ko&gl=KR&ceid=KR:ko"

    text = fetch_url(url, timeout=10)
    news_count = len(re.findall(r'<item>', text)) if text else 0

    # YouTubeの検索結果数のみチェック
    yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}&gl=KR"
    yt_text = fetch_url(yt_url, timeout=10)
    yt_count = len(re.findall(r'"videoRenderer"', yt_text)) if yt_text else 0

    # 簡易スコア計算
    quick_score = (news_count * 3) + (yt_count * 2)
    return quick_score


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
    key = f"gen7_data_kr_{gen}"

    # カテゴリでグループ化
    categories = {}
    for r in results:
        cat = r.get('category', '기타')
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(r)

    # 各カテゴリをスコア順にソート
    for cat in categories:
        categories[cat].sort(key=lambda x: x['score'], reverse=True)

    value = json.dumps({
        'generation': gen,
        'country': 'kr',
        'period': '3개월',
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
    key = f"gen7_history_kr_{gen}"
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
    key = f"gen7_history_kr_{gen}"

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
    print("韓国向け世代別トレンドデータ収集開始（拡張トレンドモード）")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: 複数ソースから新規トレンドを取得
    print("\n" + "-" * 40)
    print("Phase 1: 新規トレンド取得（複数ソース）")
    print("-" * 40)

    new_trends = fetch_all_trend_sources()

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
        # 重要: 事前に脱落させず、全て分析してから最終スコアで上位50件を決定
        keywords_to_analyze = []

        # 1. 前回のキーワードを全て継承（分析後に最終判定）
        inherited_count = 0
        for prev_kw in previous_keywords:
            kw_name = prev_kw.get('keyword', '')
            prev_score = prev_kw.get('score', 0)

            if not kw_name or not kw_name.strip():
                continue

            keywords_to_analyze.append({
                'keyword': kw_name,
                'isInherited': True,
                'prevScore': prev_score
            })
            inherited_count += 1

        print(f"  継承候補: {inherited_count}件（分析後に最終判定）")

        # 2. 新規トレンドを追加（重複除外、枠制限なしで候補追加）
        existing_kws = set(k['keyword'].lower() for k in keywords_to_analyze)

        new_trends_to_add = []
        for trend in gen_new_trends:
            if trend.lower() not in existing_kws:
                new_trends_to_add.append(trend)
                existing_kws.add(trend.lower())

        for trend in new_trends_to_add:
            keywords_to_analyze.append({
                'keyword': trend,
                'isNew': True
            })

        print(f"  新規トレンド追加: {len(new_trends_to_add)}件")

        # 3. ランダム探索（埋もれたキーワードを発掘）
        explore_count = 0
        if gen in EXPLORE_POOL:
            # 既存キーワードにないものからランダムに選択
            available_explore = [kw for kw in EXPLORE_POOL[gen] if kw.lower() not in existing_kws]
            if available_explore:
                explore_candidates = random.sample(available_explore, min(RANDOM_EXPLORE_COUNT, len(available_explore)))

                print(f"\n  ランダム探索: {len(explore_candidates)}件の候補を簡易チェック中...")
                for kw in explore_candidates:
                    try:
                        quick = quick_score_check(kw)
                        print(f"    {kw}: quick_score={quick}", end='')
                        # 簡易スコアが一定以上なら追加
                        if quick >= 20:
                            keywords_to_analyze.append({
                                'keyword': kw,
                                'isNew': True,
                                'isExplore': True
                            })
                            existing_kws.add(kw.lower())
                            explore_count += 1
                            print(" → 追加")
                        else:
                            print(" → スキップ")
                        time.sleep(0.3)
                    except Exception as e:
                        print(f" → エラー: {e}")

        print(f"  ランダム探索追加: {explore_count}件")

        # 4. シードキーワード（初回または少なすぎる場合）
        seed_count = 0
        if len(keywords_to_analyze) < 10 and gen in SEED_KEYWORDS:
            for seed in SEED_KEYWORDS[gen]:
                if seed.lower() not in existing_kws and len(keywords_to_analyze) < MAX_KEYWORDS_PER_GEN:
                    keywords_to_analyze.append({
                        'keyword': seed,
                        'isNew': True,
                        'isSeed': True
                    })
                    existing_kws.add(seed.lower())
                    seed_count += 1
            if seed_count > 0:
                print(f"  シード追加: {seed_count}件")

        print(f"  合計分析対象: {len(keywords_to_analyze)}件")

        # キーワード分析
        print(f"\n  分析実行中...")
        results = []

        for i, kw_data in enumerate(keywords_to_analyze):
            kw = kw_data['keyword']
            is_new = kw_data.get('isNew', False)
            is_explore = kw_data.get('isExplore', False)
            prefix = "🔍" if is_explore else ("🆕" if is_new else "📌")
            print(f"  [{i+1}/{len(keywords_to_analyze)}] {prefix} {kw}...", end=' ')

            try:
                result = analyze_keyword(kw)
                result['isNew'] = is_new
                result['isTrending'] = is_new
                result['isExplore'] = is_explore

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

        # スコア順にソート（最終判定：全分析結果から上位50件を選出）
        results.sort(key=lambda x: x['score'], reverse=True)

        # 最大数に制限＆脱落キーワードを表示
        if len(results) > MAX_KEYWORDS_PER_GEN:
            dropped_results = results[MAX_KEYWORDS_PER_GEN:]
            results = results[:MAX_KEYWORDS_PER_GEN]
            print(f"\n  最終選別で脱落: {len(dropped_results)}件")
            for dr in dropped_results[:10]:  # 上位10件のみ表示
                print(f"    [DROP] {dr['keyword']} (score={dr['score']})")
            if len(dropped_results) > 10:
                print(f"    ... 他{len(dropped_results) - 10}件")

        # 最終ボーダーライン表示
        if results:
            min_score = results[-1]['score']
            print(f"  ボーダーライン: score={min_score}（50位）")

        # KVに保存
        if not results:
            print(f"\n  [WARN] 分析結果が0件のためスキップ")
            continue

        print(f"\n  KVに保存中...", end=' ')
        if save_to_kv(gen, results):
            new_count = len([r for r in results if r.get('isNew')])
            explore_count = len([r for r in results if r.get('isExplore')])
            print(f"✓ {len(results)}件保存（新規{new_count}件, 探索{explore_count}件）")
        else:
            print("✗ 保存失敗")

        # 履歴保存
        print(f"  履歴を保存中...", end=' ')
        if save_score_history(gen, history_data):
            print("✓")
        else:
            print("✗ 保存失敗")

    print("\n" + "=" * 60)
    print("韓国データ収集完了（拡張トレンドモード）")
    print("=" * 60)


if __name__ == '__main__':
    main()
