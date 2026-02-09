#!/usr/bin/env python3
"""
韓国向け世代別トレンドデータ収集スクリプト
GitHub Actionsで毎日実行し、Cloudflare KVに保存

機能:
1. 事前定義キーワードの分析
2. Google Trends/Naver急上昇ワードの自動検出・メイン統合
3. 世代判定によるキーワード分類
4. 流行キーワードの自動更新
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
MAX_AUTO_TRENDS_PER_GEN = 15  # 各世代に追加する自動トレンドの最大数（メイン統合用に増加）
INTEGRATE_TRENDS_TO_MAIN = True  # 自動トレンドをメインキーワードに統合

# スコア履歴設定
HISTORY_DAYS_TO_KEEP = 30  # 保持する履歴日数

# 最大キーワード数（事前定義 + 自動トレンド）
MAX_KEYWORDS_PER_GEN = 60

# 韓国向けキーワード定義（5世代、各世代25-40キーワード）
KEYWORDS = {
    'genz': [
        # SNS・動画 (10)
        '틱톡', '유튜브 쇼츠', '인스타그램', '버튜버', '디스코드', '스레드',
        '트위치', '아프리카TV', '치지직', '라이브 방송',
        # ゲーム (10)
        '원신', '블루아카이브', '발로란트', '리그오브레전드', 'e스포츠',
        '스타레일', '메이플스토리', '로스트아크', '배틀그라운드', '던전앤파이터',
        # 音楽・エンタメ (10)
        'K-POP', '아이돌', 'BTS', 'BLACKPINK', '뉴진스', '에스파', 'IVE', '르세라핌',
        '최애', '넷플릭스',
        # ショッピング (6)
        '무신사', '올리브영', '카카오페이', '네이버페이', '당근마켓', '쿠팡',
        # キャリア・学び (6)
        '취준', '코딩', 'ChatGPT', 'AI', '인턴', '자격증',
        # ライフスタイル (4)
        '카카오톡', 'MBTI', '갓생', 'MZ세대'
    ],
    'millennial': [
        # 資産形成 (10)
        '주식투자', '부동산', '코인', '재테크', 'ETF', 'ISA', 'S&P500',
        '배당주', '연금저축펀드', '미국주식',
        # キャリア (8)
        '이직', 'N잡러', '재택근무', '프리랜서', '창업', '리스킬링', '퇴사', '워라밸',
        # 住宅 (8)
        '아파트', '전세', '청약', '대출', '내집마련', '주택담보대출', '부동산투자', '월세',
        # 育児 (6)
        '어린이집', '육아휴직', '육아', '맞벌이', '출산휴가', '양육비',
        # 健康・エンタメ (6)
        '헬스', '다이어트', '건강검진', '멘탈케어', '웹툰', '유튜브 프리미엄'
    ],
    'genx': [
        # 教育 (8)
        '입시', '수능', '학원', '교육비', '대학등록금', '과외', '학자금', '특목고',
        # 健康 (6)
        '건강검진', '암검진', '갱년기', '성인병', '고혈압', '당뇨',
        # 介護 (6)
        '부모님돌봄', '요양보험', '간병', '요양원', '요양병원', '치매',
        # キャリア・資産 (6)
        '명퇴', '조기퇴직', '퇴직금운용', '노후준비', '연금', '상속'
    ],
    'boomer': [
        # 年金・退職 (6)
        '국민연금', '퇴직연금', '정년퇴직', '재취업', '시니어일자리', '노령연금',
        # 健康 (6)
        '고혈압', '당뇨', '건강검진', '운동', '걷기', '골다공증',
        # 終活 (4)
        '웰다잉', '유언장', '상속', '장례',
        # 生活 (4)
        '여행', '취미', '스마트폰교육', '온라인쇼핑'
    ],
    'senior': [
        # 介護 (8)
        '장기요양등급', '주간보호', '방문요양', '요양보험', '요양원', '실버타운',
        '요양보호사', '재가요양',
        # 医療 (6)
        '치매', '재활', '백내장', '노인의료', '방문간호', '골다공증',
        # 補助具・終末期 (6)
        '보청기', '휠체어', '안부확인', '호스피스', '완화의료', '연명치료'
    ]
}

# 世代判定用キーワードパターン（韓国）
GENERATION_PATTERNS = {
    'genz': {
        'keywords': ['틱톡', '디스코드', '버튜버', '유튜브', '쇼츠', '인스타', '스레드', '트위치', '치지직',
                     '원신', '블루아카이브', '발로란트', '리그오브레전드', 'e스포츠', '스타레일', '메이플',
                     'K-POP', '아이돌', 'BTS', 'BLACKPINK', '뉴진스', '에스파', 'IVE', '르세라핌',
                     '무신사', '올리브영', '당근마켓', 'MZ세대', 'MBTI', '갓생', '취준', '코딩', 'ChatGPT', 'AI'],
        'age_range': (10, 27),
        'description': '1997년 이후 출생'
    },
    'millennial': {
        'keywords': ['주식투자', '부동산', '코인', '재테크', 'ETF', 'ISA', 'S&P500', '배당주', '미국주식',
                     '이직', 'N잡러', '재택근무', '프리랜서', '창업', '리스킬링', '워라밸',
                     '아파트', '전세', '청약', '대출', '내집마련', '주택담보', '월세',
                     '어린이집', '육아휴직', '육아', '맞벌이', '출산휴가', '양육비',
                     '헬스', '다이어트', '멘탈케어', '웹툰', '넷플릭스'],
        'age_range': (28, 43),
        'description': '1981-1996년 출생'
    },
    'genx': {
        'keywords': ['입시', '수능', '학원', '교육비', '대학등록금', '과외', '학자금', '특목고',
                     '건강검진', '암검진', '갱년기', '성인병', '고혈압', '당뇨',
                     '부모님돌봄', '요양보험', '간병', '요양원', '요양병원', '치매',
                     '명퇴', '조기퇴직', '퇴직금운용', '노후준비', '연금', '상속'],
        'age_range': (44, 59),
        'description': '1965-1980년 출생'
    },
    'boomer': {
        'keywords': ['국민연금', '퇴직연금', '정년퇴직', '재취업', '시니어일자리', '노령연금',
                     '고혈압', '당뇨', '운동', '걷기', '골다공증',
                     '웰다잉', '유언장', '상속', '장례', '여행', '취미', '스마트폰교육', '온라인쇼핑'],
        'age_range': (60, 74),
        'description': '1950-1964년 출생'
    },
    'senior': {
        'keywords': ['장기요양등급', '주간보호', '방문요양', '요양보험', '요양원', '실버타운',
                     '요양보호사', '재가요양', '치매', '재활', '백내장', '노인의료', '방문간호', '골다공증',
                     '보청기', '휠체어', '안부확인', '호스피스', '완화의료', '연명치료'],
        'age_range': (75, 100),
        'description': '1949년 이전 출생'
    }
}


def detect_generation(keyword):
    """키워드에서 가장 관련된 세대를 판정"""
    scores = {gen: 0 for gen in GENERATION_PATTERNS.keys()}
    keyword_lower = keyword.lower()

    for gen, pattern in GENERATION_PATTERNS.items():
        for kw in pattern['keywords']:
            if kw.lower() in keyword_lower or keyword_lower in kw.lower():
                scores[gen] += 2
            # 부분 일치도 고려
            elif any(part in keyword_lower for part in kw.lower().split()):
                scores[gen] += 1

    # 최고 점수의 세대를 반환 (동점일 경우 젊은 세대 우선)
    max_score = max(scores.values())
    if max_score == 0:
        return None  # 어느 세대에도 해당하지 않음

    gen_order = ['genz', 'millennial', 'genx', 'boomer', 'senior']
    for gen in gen_order:
        if scores[gen] == max_score:
            return gen
    return None


def fetch_google_trends_kr():
    """Google Trends 급상승 검색어 가져오기 (한국)"""
    print("\n[AUTO] Google Trends/Naver 급상승 검색어 가져오는 중...")

    trends = []

    # Google Trends RSS (한국 급상승)
    urls = [
        "https://trends.google.co.kr/trending/rss?geo=KR",
        "https://trends.google.com/trends/trendingsearches/daily/rss?geo=KR"
    ]

    for url in urls:
        try:
            text = fetch_url(url, timeout=15)
            if not text:
                continue

            # RSS에서 트렌드 워드 추출
            titles = re.findall(r'<title>(?:<!\[CDATA\[)?([^<\]]+)(?:\]\]>)?</title>', text)
            for title in titles:
                title = title.strip()
                # 필터링
                if title and len(title) > 1 and title not in ['Daily Search Trends', 'Google 트렌드', '급상승 검색어']:
                    if title not in trends:
                        trends.append(title)

            time.sleep(0.5)
        except Exception as e:
            print(f"  [WARN] Google Trends 가져오기 실패: {e}")

    # Naver 실시간 검색어에서도 가져오기 시도
    try:
        naver_url = "https://datalab.naver.com/keyword/realtimeList.naver"
        text = fetch_url(naver_url, timeout=15)
        if text:
            # 트렌드 워드 추출 (패턴 매칭)
            naver_trends = re.findall(r'"keyword"\s*:\s*"([^"]+)"', text)
            for trend in naver_trends[:20]:
                trend = trend.strip()
                if trend and len(trend) > 1 and trend not in trends:
                    trends.append(trend)
    except Exception as e:
        print(f"  [WARN] Naver 실시간 검색어 가져오기 실패: {e}")

    print(f"  → {len(trends)}건의 급상승 검색어 검출")
    return trends[:50]  # 최대 50건


def classify_trends_by_generation(trends, existing_keywords):
    """트렌드 워드를 세대별로 분류"""
    classified = {gen: [] for gen in GENERATION_PATTERNS.keys()}

    # 기존 키워드 세트 생성 (중복 체크용)
    all_existing = set()
    for gen_keywords in existing_keywords.values():
        all_existing.update(kw.lower() for kw in gen_keywords)

    for trend in trends:
        # 기존 키워드와 중복이면 스킵
        if trend.lower() in all_existing:
            continue

        # 세대 판정
        gen = detect_generation(trend)
        if gen and len(classified[gen]) < MAX_AUTO_TRENDS_PER_GEN:
            classified[gen].append(trend)
            print(f"  → [{gen}] {trend}")

    return classified


# カテゴリ分類
def categorize_keyword(keyword):
    categories = {
        'SNS・동영상': ['틱톡', '유튜브', '쇼츠', '인스타', '스트리밍', '버튜버', '스레드', '트위치', '아프리카TV', '치지직', '디스코드', '라이브'],
        '게임': ['원신', '블루아카', '발로란트', '리그오브', '게임', '메이플', '로스트아크', '배틀그라운드', '던파', '스타레일', 'e스포츠'],
        '음악・엔터': ['K-POP', '아이돌', 'BTS', '넷플릭스', '영화', '뉴진스', '에스파', 'IVE', '르세라핌', 'BLACKPINK', '최애', '웹툰'],
        '쇼핑': ['무신사', '올리브영', '쿠팡', '카카오페이', '네이버페이', '당근마켓'],
        '커리어': ['이직', 'N잡', '재택', '프리랜서', '취준', 'AI', 'ChatGPT', '코딩', '창업', '리스킬링', '퇴사', '인턴', '자격증'],
        '재테크': ['주식', '부동산', '코인', '재테크', '펀드', '연금', 'ETF', '배당주', 'ISA', 'S&P500', '미국주식'],
        '주거': ['아파트', '전세', '청약', '대출', '내집마련', '주택담보', '월세'],
        '건강・의료': ['건강검진', '암검진', '갱년기', '고혈압', '당뇨', '입원', '헬스', '다이어트', '멘탈케어', '운동', '걷기', '골다공증', '재활', '백내장'],
        '육아・가족': ['어린이집', '육아', '맞벌이', '출산휴가', '양육비', '육아휴직'],
        '요양': ['요양', '주간보호', '방문', '케어', '요양원', '치매', '간병', '실버타운', '요양보호사', '재가요양', '장기요양'],
        '웰다잉': ['웰다잉', '유언', '장례', '상속', '호스피스', '완화의료', '연명치료'],
        '라이프': ['취미', '여행', '워라밸', '갓생', 'MZ세대', '카카오톡', 'MBTI', '스마트폰교육', '온라인쇼핑'],
        '교육': ['입시', '수능', '학원', '교육비', '대학등록금', '과외', '학자금', '특목고']
    }

    for cat, keywords_list in categories.items():
        if any(k.lower() in keyword.lower() or keyword.lower() in k.lower() for k in keywords_list):
            return cat
    return '기타'


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
    """Wikipedia閲覧数を取得"""
    article = urllib.parse.quote(keyword.replace(' ', '_'))
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=days-1)
    start_str = start.strftime('%Y%m%d')
    end_str = end.strftime('%Y%m%d')

    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/ko.wikipedia/all-access/all-agents/{article}/daily/{start_str}/{end_str}"
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
    key = f"gen7_data_kr_{gen}"
    value = json.dumps({
        'country': 'kr',
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


def get_previous_scores(gen):
    """前回のスコアデータを取得"""
    key = f"gen7_data_kr_{gen}"
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}'
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            score_map = {}
            for kw in data.get('keywords', []):
                score_map[kw['keyword']] = {
                    'score': kw.get('score', 0),
                    'date': data.get('analyzedAt', '')[:10]
                }
            return score_map, data.get('analyzedAt', '')
    except Exception as e:
        print(f"  [INFO] No previous data for {gen}: {e}")
        return {}, None


def get_score_history(gen):
    """스코어 히스토리 가져오기"""
    key = f"gen7_history_kr_{gen}"
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT_ID}/storage/kv/namespaces/{CF_KV_NAMESPACE_ID}/values/{key}"
    headers = {
        'Authorization': f'Bearer {CF_API_TOKEN}'
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return {'history': {}}


def save_score_history(gen, history_data):
    """스코어 히스토리 저장"""
    key = f"gen7_history_kr_{gen}"

    # 오래된 히스토리 삭제 (30일 이상 경과)
    cutoff_date = (datetime.now() - timedelta(days=HISTORY_DAYS_TO_KEEP)).strftime('%Y-%m-%d')
    cleaned_history = {}
    for kw, dates in history_data.get('history', {}).items():
        cleaned_dates = {d: s for d, s in dates.items() if d >= cutoff_date}
        if cleaned_dates:
            cleaned_history[kw] = cleaned_dates

    value = json.dumps({
        'country': 'kr',
        'gen': gen,
        'history': cleaned_history,
        'updatedAt': datetime.now().isoformat()
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
        print(f"  [ERROR] History save failed: {e}")
        return False


def calculate_score_change(current_score, prev_scores, keyword):
    """스코어 변동 계산"""
    if keyword not in prev_scores:
        return None, None

    prev = prev_scores[keyword]
    prev_score = prev.get('score', 0)
    change = round(current_score - prev_score, 1)
    change_pct = round((change / prev_score * 100), 1) if prev_score > 0 else 0

    return change, change_pct


def save_auto_trends_to_kv(auto_trends_data):
    """자동 검출 트렌드를 KV에 저장"""
    key = "gen7_auto_trends_kr"
    value = json.dumps({
        'country': 'kr',
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
    print("韓国向け世代別トレンドデータ収集開始")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print("=" * 60)

    # Step 1: 自動トレンド検出
    auto_trends_by_gen = {}
    if AUTO_TREND_ENABLED:
        print("\n" + "-" * 40)
        print("Phase 1: 자동 트렌드 검출")
        print("-" * 40)

        # Google Trendsから急上昇ワードを取得
        trends = fetch_google_trends_kr()

        if trends:
            # 世代別に分類
            auto_trends_by_gen = classify_trends_by_generation(trends, KEYWORDS)

            # 分類結果を表示
            print("\n[AUTO] 세대별 분류 결과:")
            for gen, gen_trends in auto_trends_by_gen.items():
                if gen_trends:
                    print(f"  {gen}: {len(gen_trends)}건 - {', '.join(gen_trends[:5])}...")

    # Step 2: 事前定義キーワード + 自動トレンドの分析（統合モード）
    print("\n" + "-" * 40)
    print("Phase 2: 키워드 분석 (자동 트렌드 통합)")
    print("-" * 40)

    all_auto_trends_analyzed = {}

    for gen, keywords in KEYWORDS.items():
        # 前回のスコアを取得
        prev_scores, prev_date = get_previous_scores(gen)
        if prev_date:
            print(f"\n  이전 데이터: {prev_date[:10]} ({len(prev_scores)}키워드)")

        # スコア履歴を取得
        history_data = get_score_history(gen)
        today = datetime.now().strftime('%Y-%m-%d')

        # 自動トレンドを追加
        auto_trends = auto_trends_by_gen.get(gen, [])
        combined_keywords = list(keywords) + auto_trends

        print(f"\n[{gen}] {len(keywords)}정의 + {len(auto_trends)}자동 = {len(combined_keywords)}키워드 분석 중...")

        all_results = []  # 統合用リスト

        for i, kw in enumerate(combined_keywords):
            is_auto = i >= len(keywords)
            prefix = "🔥" if is_auto else ""
            print(f"  [{i+1}/{len(combined_keywords)}] {prefix}{kw}...", end=' ')

            try:
                result = analyze_keyword(kw)
                result['isAutoDetected'] = is_auto  # 自動検出フラグを追加
                result['isTrending'] = is_auto  # トレンドキーワードフラグ

                # スコア変動を計算
                change, change_pct = calculate_score_change(result['score'], prev_scores, kw)
                if change is not None:
                    result['scoreChange'] = change
                    result['scoreChangePct'] = change_pct
                    if prev_scores.get(kw):
                        result['prevScore'] = prev_scores[kw]['score']
                        result['prevDate'] = prev_scores[kw]['date']

                # 履歴に追加
                if kw not in history_data.get('history', {}):
                    if 'history' not in history_data:
                        history_data['history'] = {}
                    history_data['history'][kw] = {}
                history_data['history'][kw][today] = result['score']

                all_results.append(result)

                # 変動表示
                change_str = ""
                if change is not None and change != 0:
                    arrow = "↑" if change > 0 else "↓"
                    change_str = f" ({arrow}{abs(change)})"

                trend_mark = "🔥" if is_auto else ""
                print(f"✓ score={result['score']}{change_str}, refs={result['totalRefs']} {trend_mark}")
            except Exception as e:
                print(f"✗ {e}")

            time.sleep(0.3)

        # スコア順にソート（事前定義と自動トレンドを統合）
        all_results.sort(key=lambda x: x['score'], reverse=True)

        # 自動トレンドを別途記録（参照用）
        auto_results = [r for r in all_results if r.get('isAutoDetected')]
        if auto_results:
            all_auto_trends_analyzed[gen] = auto_results

        # 最大キーワード数を制限（スコア上位を保持）
        if len(all_results) > MAX_KEYWORDS_PER_GEN:
            all_results = all_results[:MAX_KEYWORDS_PER_GEN]
            print(f"  [INFO] 상위 {MAX_KEYWORDS_PER_GEN}건으로 제한")

        # KVに保存（事前定義 + 自動トレンドを統合）
        print(f"\n  KV에 저장 중 (통합)...", end=' ')
        if save_to_kv(gen, all_results):
            auto_count = len([r for r in all_results if r.get('isAutoDetected')])
            print(f"✓ {len(all_results)}건 저장 완료 (트렌드 {auto_count}건 포함)")
        else:
            print("✗ 저장 실패")

        # スコア履歴を保存
        print(f"  히스토리 저장 중...", end=' ')
        if save_score_history(gen, history_data):
            print(f"✓")
        else:
            print("✗ 저장 실패")

    # Step 3: 自動トレンド結果を別途保存
    if all_auto_trends_analyzed:
        print("\n" + "-" * 40)
        print("Phase 3: 자동 트렌드 결과 저장")
        print("-" * 40)

        print("  자동 검출 트렌드를 KV에 저장 중...", end=' ')
        if save_auto_trends_to_kv(all_auto_trends_analyzed):
            total_auto = sum(len(v) for v in all_auto_trends_analyzed.values())
            print(f"✓ {total_auto}건 저장 완료")
        else:
            print("✗ 저장 실패")

    print("\n" + "=" * 60)
    print("韓国データ収集完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
