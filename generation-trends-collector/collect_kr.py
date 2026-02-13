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
RANDOM_EXPLORE_COUNT = 5  # ランダム探索で試すキーワード数
HISTORY_DAYS_TO_KEEP = 30  # 保持する履歴日数

# カテゴリ動的管理の設定
OTHER_CATEGORY_THRESHOLD = 5  # 「기타」がこの数を超えたら新カテゴリを検討
MIN_CATEGORY_KEYWORDS = 2  # この数未満のカテゴリは統合候補
AUTO_CATEGORY_MIN_KEYWORDS = 3  # 自動カテゴリ生成に必要な最小キーワード数

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
# カテゴリ分類パターン（韓国版・拡充版）
CATEGORY_PATTERNS = {
    'SNS・동영상': [
        '틱톡', 'TikTok', '유튜브', 'YouTube', '쇼츠', 'Shorts', '인스타', 'Instagram', '인스타그램',
        '라이브', '방송', '버튜버', 'VTuber', '트위치', 'Twitch', '아프리카', 'AfreecaTV', '치지직',
        '디스코드', 'Discord', '스레드', 'Threads', '카카오톡', '카톡', 'X', '트위터', 'Twitter',
        '고세구', '주르르', '징버거', '우왁굳', '침착맨', '대도서관', '피식대학', '숏박스', '침투부',
        '구독', '채널', '스트리머', '크리에이터', '컨텐츠', 'SNS', '소셜'
    ],
    '게임': [
        '원신', '블루아카이브', '블루아카', '발로란트', 'Valorant', 'LoL', '롤', '리그오브레전드',
        '포켓몬', '젤다', 'e스포츠', '이스포츠', '메이플', '메이플스토리', '오버워치', '게임', 'PC방',
        '스팀', 'Steam', '젠레스존제로', 'ZZZ', '학원아이돌마스터', '학마스', '우마무스메',
        '프로세카', 'FGO', '붕괴스타레일', '붕스', '명일방주', '포트나이트', 'Fortnite',
        '마인크래프트', '마크', '동물의숲', '모동숲', '배틀그라운드', 'PUBG', '서든어택',
        '로스트아크', '던파', '리니지', '검은사막', '피파', 'FIFA', 'EA', '닌텐도', 'Nintendo',
        '플레이스테이션', 'PS5', 'Xbox', '스위치', 'Switch', '철권', 'Tekken', '카트라이더',
        '넥슨', 'NC', '넷마블', '크래프톤', '스마일게이트', '펄어비스', '가챠', '리세마라'
    ],
    '음악・엔터': [
        'BTS', '방탄', '아이브', 'IVE', '에스파', 'aespa', '뉴진스', 'NewJeans', 'K-POP', 'KPOP',
        '아이돌', '덕질', '콘서트', '팬미팅', '드라마', '영화', '넷플릭스', 'Netflix', '예능',
        '르세라핌', 'LE SSERAFIM', '스테이씨', 'STAYC', '잇지', 'ITZY', '엔시티', 'NCT',
        '세븐틴', 'SEVENTEEN', '스트레이키즈', 'Stray Kids', '아이유', 'IU', '태연', '백현',
        '임영웅', '이무진', '아이들', '(G)I-DLE', '블랙핑크', 'BLACKPINK', '트와이스', 'TWICE',
        'SM', 'YG', 'JYP', 'HYBE', '하이브', '빅히트', '엔터테인먼트', '소속사', '데뷔', '컴백',
        '음원', '차트', '멜론', 'Melon', '지니', 'Genie', '스포티파이', 'Spotify', '유튜브뮤직',
        '만화', '웹툰', '네이버웹툰', '카카오웹툰', '애니메이션', '애니', '오타쿠', '덕후'
    ],
    '쇼핑・결제': [
        '당근마켓', '당근', '쿠팡', 'Coupang', '무신사', 'MUSINSA', '카카오페이', '네이버페이',
        '편의점', 'GS25', 'CU', '세븐일레븐', '이마트', '롯데마트', '홈플러스', '코스트코',
        '할인', '세일', '포인트', '쇼핑', '직구', '해외직구', '알리', '알리익스프레스', 'AliExpress',
        '테무', 'Temu', '아마존', 'Amazon', '지마켓', '옥션', '11번가', 'SSG', '신세계',
        '현대백화점', '롯데백화점', '아울렛', '면세점', '올리브영', '다이소', '이케아', 'IKEA',
        '유니클로', 'UNIQLO', '자라', 'ZARA', 'H&M', '탑텐', '스파오'
    ],
    '커리어・학습': [
        '이직', '퇴사', '재택', '재택근무', '프리랜서', '취준', '취준생', '취업준비',
        '자소서', '자기소개서', '코딩', '개발자', 'AI', 'ChatGPT', '인공지능', '자격증',
        '공무원', '공시', '스펙', '면접', '연봉', '월급', '성과급', '워라밸', '야근',
        '노션', 'Notion', '웹디자인', '영상편집', '캔바', 'Canva', '토익', 'TOEIC', '토플',
        '파이썬', 'Python', '자바', 'Java', '코딩테스트', '알고리즘', '부트캠프', '국비지원',
        '클래스101', '탈잉', '크몽', '숨고', 'N잡', '투잡', '부업', '사이드프로젝트'
    ],
    '재테크・투자': [
        '주식', '코인', '비트코인', 'BTC', '이더리움', 'ETH', '부동산', 'ETF', '적금', '예금',
        '청약', '대출', '투자', '재테크', '연금', '상속', '증여', 'ISA', 'IRP', '퇴직연금',
        'S&P500', '나스닥', 'NASDAQ', '배당주', '미국주식', '해외주식', '국내주식',
        '토스증권', '카카오증권', 'KB증권', '삼성증권', '미래에셋', '키움증권', 'NH투자',
        '금리', '환율', '달러', '엔화', '환전', '물가', '인플레이션', '절세', '세금', '연말정산'
    ],
    '부동산': [
        '아파트', '전세', '월세', '청약', '분양', '재개발', '재건축', '이사', '부동산',
        '매매', '계약', '복비', '중개', '다주택', '임대', '전월세', '보증금', '주담대',
        '신축', '구축', '빌라', '오피스텔', '원룸', '투룸', '주택', '서울', '수도권', '지방'
    ],
    '건강・의료': [
        '건강검진', '암검진', '종합검진', '갱년기', '고혈압', '당뇨', '당뇨병', '헬스', '헬스장',
        '다이어트', '필라테스', '요가', '정신건강', '우울증', '불안', '피부', '피부과', '치매',
        '재활', '물리치료', '병원', '의사', '약', '처방', '수술', '입원', '건강보험', '실비',
        '애니타임', '스포애니', '짐박스', '홈트', '간헐적단식', '프로틴', '단백질', '비타민',
        '영양제', '보톡스', '필러', '레이저', '성형', '쌍꺼풀', '코수술', '눈성형', '피부관리'
    ],
    '육아・가족': [
        '육아', '어린이집', '유치원', '출산', '임신', '맞벌이', '손주', '결혼', '신혼',
        '육아휴직', '출산휴가', '아기', '신생아', '이유식', '분유', '기저귀', '유모차',
        '아동수당', '양육비', '학원비', '교육비', '초등학교', '중학교', '고등학교',
        '웅진씽크빅', '눈높이', '밀크티', '엘리하이', '학습지', '과외', '학원'
    ],
    '돌봄': [
        '요양원', '요양병원', '요양등급', '장기요양', '주간보호', '방문요양', '방문간호',
        '간병', '간병인', '치매', '치매환자', '돌봄', '노인정', '경로당', '복지관',
        '장애인', '장애등급', '활동지원', '활동보조', '사회복지사', '요양보호사'
    ],
    '종활': [
        '유언장', '상속', '상속세', '증여세', '장례', '장례식', '묘지', '납골당', '화장',
        '호스피스', '임종', '연명치료', '사전연명의료', '존엄사', '생전정리'
    ],
    '라이프': [
        'MBTI', '카페', '맛집', '여행', '해외여행', '국내여행', '취미', '반려동물', '반려견',
        '반려묘', '강아지', '고양이', '인테리어', '집꾸미기', '이사', '원룸꾸미기',
        '캠핑', '글램핑', '등산', '러닝', '골프', '테니스', '서핑', '낚시', '사우나', '찜질방',
        '술집', '바', '클럽', '파티', '소개팅', '데이팅앱', '틴더', '아만다', '정오의데이트'
    ],
    '교육': [
        '입시', '대입', '수능', '학원', '과외', '교육비', '유학', '어학연수', '영어', '영어학원',
        '대성마이맥', '메가스터디', '이투스', 'EBS', '수시', '정시', '학생부', '내신',
        '스카이', 'SKY', '인서울', '의대', '의대입시', '자사고', '특목고', '영재고',
        '수학', '국어', '과학', '사회', '논술', '면접', '합격', '불합격', '정시컷', '등급컷'
    ],
    '뉴스・사회': [
        '선거', '대선', '총선', '정치', '대통령', '국회', '여당', '야당', '민주당', '국민의힘',
        '법안', '법률', '재판', '판결', '검찰', '경찰', '사건', '사고', '뉴스', '속보',
        '경제', '물가', '금리', '환율', '인플레이션', '불경기', '호황', '실업', '취업률'
    ],
    '스포츠': [
        '야구', 'KBO', '축구', 'K리그', '농구', 'KBL', '배구', 'V리그', '골프', 'LPGA', 'PGA',
        '올림픽', '월드컵', '아시안게임', '손흥민', '이강인', '김하성', '오타니', '류현진',
        '이정후', 'MLB', 'EPL', '프리미어리그', '라리가', '분데스리가', '세리에A', 'UFC', '격투기'
    ]
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
    """トレンドワードを世代別に分類（上限なし、最終的にスコアで選別）"""
    classified = {gen: [] for gen in GENERATION_PATTERNS.keys()}

    for trend in trends:
        # 既存キーワードと重複していたらスキップ
        if trend.lower() in existing_keywords_set:
            continue

        # 世代を判定
        gen = detect_generation(trend)
        if gen:
            classified[gen].append(trend)

    return classified


def categorize_keyword(keyword):
    """キーワードをカテゴリに分類（スコアリング方式）"""
    keyword_lower = keyword.lower()
    scores = {}

    for cat, patterns in CATEGORY_PATTERNS.items():
        score = 0
        for p in patterns:
            p_lower = p.lower()
            # 完全一致（最高スコア）
            if keyword_lower == p_lower:
                score += 10
            # キーワードにパターンが含まれる
            elif p_lower in keyword_lower:
                # 長いパターンほど高スコア（より具体的なマッチ）
                score += 3 + len(p_lower) // 3
            # パターンにキーワードが含まれる
            elif keyword_lower in p_lower:
                score += 2

        if score > 0:
            scores[cat] = score

    # 最高スコアのカテゴリを返す
    if scores:
        return max(scores, key=scores.get)
    return '기타'


def extract_common_words(keywords):
    """キーワード群から共通する単語を抽出"""
    word_count = {}
    for kw in keywords:
        # 韓国語の単語を抽出（ハングル、英語）
        words = re.findall(r'[가-힣]{2,}|[A-Za-z]{3,}', kw)
        for word in words:
            word_lower = word.lower()
            if len(word_lower) >= 2:
                word_count[word_lower] = word_count.get(word_lower, 0) + 1

    # 2回以上出現する単語を返す
    common = [(w, c) for w, c in word_count.items() if c >= 2]
    return sorted(common, key=lambda x: x[1], reverse=True)


def suggest_category_name(keywords):
    """キーワード群から適切なカテゴリ名を提案"""
    common_words = extract_common_words(keywords)
    if common_words:
        # 最も頻出する単語をカテゴリ名に
        return common_words[0][0].capitalize()

    # 共通単語がない場合は最初のキーワードから
    if keywords:
        first_kw = keywords[0]
        words = re.findall(r'[가-힣]{2,}|[A-Za-z]{3,}', first_kw)
        if words:
            return words[0]

    return None


def guess_category_by_pattern(keyword):
    """キーワードのパターンからカテゴリを推測"""
    # 除外ワード（これらは人名ではない）
    non_person_words = [
        '정년', '보험', '연금', '자금', '증여', '상속', '간병', '의료', '수술', '검진',
        '증상', '치료', '장애', '녹내장', '백내장', '당뇨', '고혈압', '대출', '주택',
        '투자', '주식', '퇴직', '종신', '노후', '생전', '유산', '시설', '병원', '센터',
        '학원', '학교', '대학', '입시', '수능', '공무원'
    ]

    # 除外チェック
    for word in non_person_words:
        if word in keyword:
            return None

    # 人名・タレント関連のパターン（職業名を含む場合のみ）
    celebrity_job_patterns = ['배우', '가수', '아이돌', '코미디언', '개그맨', 'MC', '아나운서', '모델', '감독', '작가']

    for pattern in celebrity_job_patterns:
        if pattern in keyword:
            return '연예・유명인'

    # 地域・場所関連（より厳密なパターン）
    location_suffix_patterns = ['지역', '반도', '공항', '특별시', '광역시', '도청']
    for pattern in location_suffix_patterns:
        if pattern in keyword:
            return '지역・장소'

    # 「〇〇시」「〇〇군」「〇〇구」の形式（末尾にある場合のみ、2文字以上の地名）
    if re.search(r'.{2,}[시군구]$', keyword) and len(keyword) >= 3:
        return '지역・장소'

    # テクノロジー・企業関連
    tech_patterns = ['Google', 'Apple', 'Microsoft', 'Amazon', 'Meta', 'Facebook', 'OpenAI', 'Anthropic',
                     'React', 'Python', 'Java', 'API', 'SDK', 'DeepSeek', 'Claude', 'Gemini', 'GPT', 'LLM']

    keyword_lower = keyword.lower()
    for pattern in tech_patterns:
        if pattern.lower() == keyword_lower or pattern.lower() in keyword_lower:
            return '테크놀로지'

    # 人名の推測は無効化（誤検出が多いため）
    # 韓国の人名は通常3文字だが、一般名詞と区別が困難なため推測しない

    return None


def analyze_category_health(results):
    """カテゴリの健全性を分析し、動的に調整"""
    global CATEGORY_PATTERNS

    # カテゴリ別にキーワードを集計
    category_keywords = {}
    other_keywords = []

    for r in results:
        cat = r.get('category', '기타')
        kw = r.get('keyword', '')
        if cat == '기타':
            other_keywords.append(kw)
        else:
            if cat not in category_keywords:
                category_keywords[cat] = []
            category_keywords[cat].append(kw)

    changes_made = []

    # 1. 「기타」が多すぎる場合 → カテゴリを推測して再分類
    if len(other_keywords) >= OTHER_CATEGORY_THRESHOLD:
        print(f"\n  [카테고리 분석] 「기타」가 {len(other_keywords)}건 - 재분류 시도 중...")

        # まず、パターンベースで再分類を試みる
        reclassified = {}
        remaining_others = []

        for kw in other_keywords:
            guessed_cat = guess_category_by_pattern(kw)
            if guessed_cat:
                if guessed_cat not in reclassified:
                    reclassified[guessed_cat] = []
                reclassified[guessed_cat].append(kw)
            else:
                remaining_others.append(kw)

        # 推測されたカテゴリを適用
        for cat_name, keywords in reclassified.items():
            if len(keywords) >= 2:  # 2件以上あれば新カテゴリとして採用
                if cat_name not in CATEGORY_PATTERNS:
                    CATEGORY_PATTERNS[cat_name] = []
                CATEGORY_PATTERNS[cat_name].extend(keywords)
                changes_made.append(f"「{cat_name}」에 {len(keywords)}건 분류")
                print(f"    → 「{cat_name}」에 분류: {keywords[:5]}...")

                # 対象キーワードのカテゴリを更新
                for r in results:
                    if r.get('keyword', '') in keywords:
                        r['category'] = cat_name

        other_keywords = remaining_others

        # 共通パターンを探す（残りのキーワード）
        if len(other_keywords) >= AUTO_CATEGORY_MIN_KEYWORDS:
            common_words = extract_common_words(other_keywords)

            for word, count in common_words[:3]:  # 上位3つまで検討
                if count >= AUTO_CATEGORY_MIN_KEYWORDS:
                    # この単語を含むキーワードを抽出
                    matching_keywords = [kw for kw in other_keywords if word.lower() in kw.lower()]

                    if len(matching_keywords) >= AUTO_CATEGORY_MIN_KEYWORDS:
                        # 新カテゴリを生成
                        new_cat_name = word.capitalize()

                        # 既存カテゴリと重複しないか確認
                        if new_cat_name not in CATEGORY_PATTERNS:
                            CATEGORY_PATTERNS[new_cat_name] = matching_keywords.copy()
                            changes_made.append(f"새 카테고리 「{new_cat_name}」 생성 ({len(matching_keywords)}건)")
                            print(f"    → 새 카테고리 「{new_cat_name}」 생성: {matching_keywords[:5]}...")

                            # 対象キーワードのカテゴリを更新
                            for r in results:
                                if r.get('keyword', '') in matching_keywords:
                                    r['category'] = new_cat_name

                            # other_keywordsから削除
                            for kw in matching_keywords:
                                if kw in other_keywords:
                                    other_keywords.remove(kw)

    # 2. キーワードが少なすぎるカテゴリ → 統合または削除を検討
    empty_categories = []
    small_categories = []

    for cat in CATEGORY_PATTERNS.keys():
        count = len(category_keywords.get(cat, []))
        if count == 0:
            empty_categories.append(cat)
        elif count < MIN_CATEGORY_KEYWORDS:
            small_categories.append((cat, count))

    if empty_categories:
        print(f"\n  [카테고리 분석] 빈 카테고리: {empty_categories}")

    if small_categories:
        print(f"  [카테고리 분석] 키워드가 적은 카테고리: {small_categories}")
        # 小さいカテゴリは「라이프」に統合を検討
        for cat, count in small_categories:
            if cat not in ['종활', '돌봄', '교육']:  # 重要カテゴリは維持
                keywords_to_merge = category_keywords.get(cat, [])
                if keywords_to_merge and '라이프' in CATEGORY_PATTERNS:
                    # 統合先にパターンを追加
                    CATEGORY_PATTERNS['라이프'].extend(keywords_to_merge)
                    changes_made.append(f"「{cat}」({count}건)을 「라이프」에 통합")
                    print(f"    → 「{cat}」을 「라이프」에 통합")

                    # 対象キーワードのカテゴリを更新
                    for r in results:
                        if r.get('category', '') == cat:
                            r['category'] = '라이프'

    return changes_made


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

        # カテゴリの動的管理（「기타」が多い場合に新カテゴリを自動生成）
        category_changes = analyze_category_health(results)
        if category_changes:
            print(f"  카테고리 변경: {len(category_changes)}건")

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
