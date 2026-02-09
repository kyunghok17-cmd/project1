#!/usr/bin/env python3
"""
韓国向け世代別トレンドデータ収集スクリプト
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


def main():
    print("=" * 60)
    print("韓国向け世代別トレンドデータ収集開始")
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
    print("韓国データ収集完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
