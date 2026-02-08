#!/usr/bin/env python3
"""
世代別トレンドデータ収集スクリプト
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

# 環境変数から設定を取得（ローカル実行時はデフォルト値使用）
CF_API_TOKEN = os.environ.get('CF_API_TOKEN') or "HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U"
CF_ACCOUNT_ID = os.environ.get('CF_ACCOUNT_ID') or "dddb47cb848a3a6100f19fdcd6811212"
CF_KV_NAMESPACE_ID = os.environ.get('CF_KV_NAMESPACE_ID') or "f5c396bf00af493abad3568261143511"
WORKER_URL = os.environ.get('WORKER_URL', 'https://generation-trends.kyunghok17.workers.dev')

# SSL証明書検証をスキップ（一部環境用）
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# 世代別キーワード定義（メイン50+ / 予備30+）
KEYWORDS = {
    'jp': {
        'genz': [
            # SNS・動画 (10)
            'TikTok', 'YouTube Shorts', 'BeReal', 'Instagram', 'VTuber',
            'にじさんじ', 'ホロライブ', 'ライブ配信', '切り抜き動画', 'ストリーマー',
            # ゲーム (10)
            '原神', 'ブルーアーカイブ', 'Valorant', 'Apex Legends', 'ポケモン',
            'スプラトゥーン3', 'ゼルダの伝説', 'FF16', 'ストリートファイター6', 'eスポーツ',
            # 音楽・エンタメ (10)
            'YOASOBI', 'Ado', 'ボカロ', 'Spotify', '米津玄師',
            'アニメ映画', '声優', '推し活', 'ライブ', 'フェス',
            # ファッション・消費 (8)
            'メルカリ', 'PayPay', 'SHEIN', 'ユニクロ', 'GU',
            'フリマアプリ', 'ネット通販', 'サステナブルファッション',
            # コミュニケーション (6)
            'Discord', 'LINE', 'Twitter', 'オープンチャット', 'MBTI', 'タイパ',
            # 学び・キャリア (8)
            '就活', 'インターン', 'プログラミング学習', 'ChatGPT', 'AI',
            '資格', 'オンライン学習', '起業'
        ],
        'millennial': [
            # 資産形成 (10)
            'NISA', 'iDeCo', '積立投資', '株式投資', '投資信託',
            'FIRE', '資産形成', '不動産投資', '仮想通貨', 'FX',
            # キャリア (10)
            '転職', '副業', 'リモートワーク', 'フリーランス', 'キャリアアップ',
            'スキルアップ', 'MBA', 'リスキリング', 'コーチング', '起業',
            # 住宅・生活 (10)
            'マンション購入', '住宅ローン', 'ふるさと納税', 'ポイ活', '家計管理',
            '節約', 'コストコ', 'IKEA', 'インテリア', '引っ越し',
            # 育児・家族 (8)
            '保育園', '育児休暇', 'ワンオペ育児', '子育て支援', '幼児教育',
            '習い事', 'ベビー用品', 'マタニティ',
            # 健康・美容 (6)
            'ジム', 'ダイエット', 'メンタルヘルス', '睡眠改善', 'サプリ', 'スキンケア',
            # エンタメ (8)
            'Netflix', 'Amazon Prime', 'Disney+', 'サブスク', 'ポッドキャスト',
            'オーディオブック', '映画', 'ドラマ'
        ],
        'genx': [
            # 教育費 (10)
            '中学受験', '大学受験', '塾', '予備校', '教育費',
            '学資保険', '奨学金', '私立学校', '受験勉強', '進学',
            # 住宅 (8)
            'リフォーム', 'マンション売却', '住み替え', '固定資産税', '持ち家',
            '住宅ローン借り換え', 'バリアフリー', '二世帯住宅',
            # 健康 (10)
            '人間ドック', 'がん検診', '更年期', '老眼', '高血圧',
            '生活習慣病', 'メタボ', '糖尿病予防', '運動不足', '健康診断',
            # 介護 (10)
            '親の介護', '介護保険', '介護離職', 'ケアマネジャー', '介護施設',
            'デイサービス', '訪問介護', '介護休暇', '遠距離介護', '介護費用',
            # キャリア (6)
            '役職定年', '早期退職', '転職40代', 'リスキリング', '管理職', '昇進',
            # 資産 (8)
            '退職金運用', '生命保険', '相続対策', '老後資金', '年金',
            '資産運用', '節税', '確定申告'
        ],
        'boomer': [
            # 年金・退職 (10)
            '年金受給', '退職金', '定年退職', '再雇用', '年金額',
            '厚生年金', '国民年金', '年金繰り下げ', '退職後', 'シニア就職',
            # 健康 (10)
            '高血圧', '糖尿病', '健康診断', '運動習慣', '血圧',
            'コレステロール', '骨密度', '認知症予防', '脳トレ', 'ウォーキング',
            # 医療 (8)
            '医療保険', '入院', '手術', 'かかりつけ医', '薬',
            '通院', '検査', '医療費',
            # 終活 (10)
            '終活', '遺言書', '相続', 'エンディングノート', '墓',
            '葬儀', '生前整理', '断捨離', '遺産', '家族信託',
            # 生活 (8)
            'シニア割引', '旅行', '趣味', 'ボランティア', '孫',
            '家族旅行', '帰省', '同窓会',
            # デジタル (6)
            'スマホ教室', 'LINE使い方', 'オンライン診療', 'ネットショッピング',
            'キャッシュレス', 'マイナンバー'
        ],
        'senior': [
            # 介護 (12)
            '介護認定', 'デイサービス', '訪問介護', 'ショートステイ', '介護保険',
            '要介護', '要支援', 'ケアプラン', '福祉用具', '介護サービス',
            'ヘルパー', '介護タクシー',
            # 施設 (10)
            '特別養護老人ホーム', '有料老人ホーム', 'グループホーム', 'サ高住', '老人ホーム',
            'ケアハウス', '介護付きマンション', '入所', '入居', '施設選び',
            # 医療 (10)
            '後期高齢者医療', '白内障手術', '骨粗しょう症', 'リハビリ', '認知症',
            '物忘れ', '難聴', '転倒予防', '誤嚥', '訪問診療',
            # 補助具 (6)
            '補聴器', '杖', '車椅子', '介護ベッド', '歩行器', '手すり',
            # 在宅 (6)
            '在宅医療', '訪問看護', 'ホームヘルパー', '配食サービス', '見守り', '安否確認',
            # 終末期 (8)
            '看取り', 'ホスピス', '緩和ケア', '延命治療', '終末期医療',
            '尊厳死', 'ACP', 'リビングウィル'
        ]
    },
    'kr': {
        'genz': [
            '틱톡', '유튜브 쇼츠', '인스타그램', '버튜버', '스트리밍',
            '원신', '블루아카이브', '발로란트', '리그오브레전드', 'e스포츠',
            'K-POP', '아이돌', 'BTS', 'BLACKPINK', '최애',
            '무신사', '올리브영', '다이소', '카카오페이', '네이버페이',
            '디스코드', '카카오톡', 'MBTI', '갓생', 'MZ세대',
            '취준', '인턴', '코딩', 'ChatGPT', 'AI'
        ],
        'millennial': [
            '주식투자', '부동산', '코인', '재테크', 'ETF',
            '이직', 'N잡러', '재택근무', '프리랜서', '창업',
            '아파트', '전세', '청약', '대출', '내집마련',
            '어린이집', '육아휴직', '맞벌이', '육아', '워라밸',
            '헬스', '다이어트', '멘탈케어', '수면', '건강검진',
            '넷플릭스', '디즈니플러스', '유튜브 프리미엄', '구독서비스', '웹툰'
        ],
        'genx': [
            '입시', '수능', '학원', '교육비', '대학등록금',
            '리모델링', '아파트매매', '재산세', '주택담보대출', '전세대출',
            '건강검진', '암검진', '갱년기', '노안', '성인병',
            '부모님돌봄', '요양보험', '간병', '케어매니저', '요양원',
            '명퇴', '조기퇴직', '40대이직', '재교육', '자격증',
            '펀드', '퇴직금운용', '보험', '상속대비', '노후준비'
        ],
        'boomer': [
            '국민연금', '퇴직연금', '정년퇴직', '재취업', '시니어일자리',
            '고혈압', '당뇨', '건강검진', '운동', '걷기',
            '의료보험', '입원', '수술', '주치의', '약',
            '웰다잉', '유언장', '상속', '증여', '장례',
            '시니어할인', '여행', '취미', '봉사활동', '손주',
            '스마트폰교육', '카카오톡', '비대면진료', '온라인쇼핑', '키오스크'
        ],
        'senior': [
            '장기요양등급', '주간보호', '방문요양', '단기보호', '요양보험',
            '요양원', '유료양로원', '그룹홈', '실버타운', '요양시설',
            '노인의료', '백내장', '골다공증', '재활', '치매',
            '보청기', '지팡이', '휠체어', '요양침대', '보행기',
            '재가요양', '방문간호', '요양보호사', '도시락배달', '안부확인',
            '임종', '호스피스', '완화의료', '연명치료', '장례'
        ]
    }
}

# 予備キーワードプール（除外時の補充用）
RESERVE_KEYWORDS = {
    'jp': {
        'genz': [
            'Threads', 'Bluesky', 'Mastodon', 'Twitch', 'SHOWROOM',
            'モンスト', 'パズドラ', 'ウマ娘', 'プロセカ', 'あんスタ',
            'King Gnu', 'Official髭男dism', 'Mrs. GREEN APPLE', 'Vaundy', 'imase',
            'Z世代', 'α世代', 'デジタルネイティブ', 'インフルエンサー', 'クリエイター',
            'Notion', 'Canva', 'Figma', 'GitHub', 'Duolingo',
            'コスパ', 'エモい', 'バズる', '映え', 'チル'
        ],
        'millennial': [
            '新NISA', 'S&P500', 'オルカン', '高配当株', 'インデックス投資',
            'Uber Eats', '出前館', 'Wolt', 'タイムズカー', 'カーシェア',
            'ワーケーション', 'ノマド', 'デジタルノマド', 'パラレルキャリア', '複業',
            'モンテッソーリ', 'STEAM教育', '中学受験', 'プレスクール', '療育',
            'ピラティス', 'ヨガ', 'クロスフィット', 'ランニング', 'マラソン',
            'U-NEXT', 'Hulu', 'ABEMA', 'Kindle Unlimited', 'Audible'
        ],
        'genx': [
            '50代転職', 'セカンドキャリア', '定年準備', 'ライフシフト', '55歳の壁',
            '膝痛', '腰痛', '肩こり', '頭痛', '不眠症',
            '認知症介護', 'ダブルケア', '介護うつ', '介護疲れ', 'ケアラー',
            '空き家', '実家じまい', '遺品整理', '不動産売却', '賃貸経営',
            '老後2000万円', '資産寿命', '運用利回り', '個人年金', '変額保険',
            '趣味探し', 'セカンドライフ', '生きがい', '50代からの', '人生100年'
        ],
        'boomer': [
            '繰り上げ受給', '繰り下げ受給', '加給年金', '在職老齢年金', '遺族年金',
            '後期高齢者', '限度額適用認定', '高額療養費', '傷病手当金', '介護医療院',
            '成年後見人', '任意後見', '法定後見', '身元保証', 'おひとりさま',
            '家庭菜園', 'ウォーキング', '体操教室', '公民館', 'シルバー人材',
            'ガラケー', 'らくらくスマホ', 'タブレット', 'Zoom', 'ビデオ通話',
            '詐欺対策', '特殊詐欺', '還付金詐欺', 'オレオレ詐欺', '架空請求'
        ],
        'senior': [
            '要介護認定', '区分変更', '介護度', 'ADL', 'IADL',
            '介護医療院', '老健', '特養待ち', '入所待機', 'ロングショート',
            '訪問リハビリ', '通所リハビリ', '小規模多機能', '看護小規模多機能', '定期巡回',
            '成年後見制度', '日常生活自立支援事業', '権利擁護', '虐待防止', '身体拘束',
            '経管栄養', '胃ろう', '吸引', '褥瘡', 'ターミナル',
            'サービス付き高齢者向け住宅', '住宅型有料老人ホーム', '介護付有料老人ホーム', '軽費老人ホーム', '養護老人ホーム'
        ]
    },
    'kr': {
        'genz': [
            '스레드', '블루스카이', '트위치', '아프리카TV', '치지직',
            '메이플스토리', '던전앤파이터', '로스트아크', '리니지', '배틀그라운드',
            '뉴진스', '에스파', 'IVE', '르세라핌', '스테이씨',
            'MZ세대', '잘파세대', '디지털네이티브', '인플루언서', '크리에이터'
        ],
        'millennial': [
            '미국주식', 'ETF', '배당주', 'ISA', '연금저축펀드',
            '쿠팡이츠', '배달의민족', '요기요', '카카오T', '쏘카',
            '워케이션', '프리랜서', '디지털노마드', '겸업', '투잡'
        ],
        'genx': [
            '50대이직', '세컨드커리어', '정년준비', '라이프시프트', '55세벽',
            '무릎통증', '허리통증', '어깨결림', '두통', '불면증',
            '치매간병', '더블케어', '간병우울', '간병피로', '케어러'
        ],
        'boomer': [
            '조기수령', '연기수령', '유족연금', '노령연금', '장애연금',
            '후기고령자', '본인부담상한제', '고액요양비', '상병수당', '요양병원'
        ],
        'senior': [
            '요양등급', '등급변경', '일상생활수행능력', '인지기능',
            '요양병원', '노인전문병원', '대기자', '입소대기', '단기입소'
        ]
    }
}

# カテゴリ分類
def categorize_keyword(keyword, country):
    categories = {
        'jp': {
            'SNS・動画': ['TikTok', 'YouTube', 'Shorts', 'BeReal', 'Instagram', '配信', '切り抜き', 'VTuber', 'ライブ', 'ストリーマー', 'にじさんじ', 'ホロライブ'],
            'ゲーム': ['原神', 'ブルアカ', 'Valorant', 'Apex', 'ポケモン', 'スプラ', 'ゼルダ', 'FF', 'スト6', 'eスポーツ', 'ゲーム'],
            '音楽・エンタメ': ['YOASOBI', 'Ado', 'ボカロ', 'Spotify', '米津', '音楽', '声優', 'アニメ', 'Netflix', '映画', 'ドラマ', 'ライブ', 'フェス', '推し活'],
            'ショッピング・決済': ['メルカリ', 'PayPay', 'SHEIN', '通販', 'フリマ', 'Amazon', '楽天', 'コストコ', 'IKEA', 'ユニクロ', 'GU'],
            'キャリア・学び': ['転職', '副業', 'リモート', 'フリーランス', '就活', 'インターン', 'プログラミング', 'AI', 'ChatGPT', 'リスキリング', 'スキル', 'MBA', '起業', '資格'],
            '資産・投資': ['NISA', 'iDeCo', '投資', '株', '退職金', '年金', '資産', '相続', 'FIRE', 'FX', '仮想通貨', '不動産投資'],
            '住宅': ['マンション', '住宅ローン', 'リフォーム', '住み替え', '固定資産', '持ち家', '引っ越し', '二世帯'],
            '健康・医療': ['人間ドック', 'がん', '検診', '更年期', '老眼', '高血圧', '糖尿病', '入院', '手術', '白内障', '骨粗しょう症', 'メタボ', '生活習慣病', '健康診断', 'ジム', 'ダイエット'],
            '育児・家族': ['保育園', '育児', 'ワンオペ', '子育て', '孫', '結婚', '家族', '帰省', 'ベビー', 'マタニティ', '習い事'],
            '教育': ['中学受験', '大学受験', '塾', '予備校', '教育費', '学資', '奨学金', '私立', '進学'],
            '介護': ['介護', 'デイサービス', '訪問', 'ケアマネ', '老人ホーム', '特養', 'グループホーム', '認知症', '要介護', 'ヘルパー'],
            '終活': ['終活', '遺言', 'エンディング', '葬儀', '墓', '看取り', 'ホスピス', '相続', '遺産', '断捨離'],
            'ライフスタイル': ['ポイ活', 'ふるさと納税', '節約', 'サブスク', '旅行', 'キャンプ', '趣味', 'ボランティア', 'SDGs', 'タイパ'],
            'コミュニケーション': ['Discord', 'LINE', 'Twitter', 'SNS', 'MBTI', 'オープンチャット'],
            'シニア生活': ['シニア割引', '年金', '再雇用', '定年', 'スマホ教室', 'オンライン診療']
        },
        'kr': {
            'SNS・동영상': ['틱톡', '유튜브', '쇼츠', '인스타', '스트리밍', '버튜버'],
            '게임': ['원신', '블루아카', '발로란트', '리그오브', '게임', 'e스포츠'],
            '음악・엔터': ['K-POP', '아이돌', 'BTS', 'BLACKPINK', '넷플릭스', '영화', '웹툰'],
            '쇼핑': ['무신사', '올리브영', '쿠팡', '카카오페이', '네이버페이', '다이소'],
            '커리어': ['이직', 'N잡', '재택', '프리랜서', '취준', 'AI', '코딩', '창업'],
            '재테크': ['주식', '부동산', '코인', '재테크', '펀드', '연금', 'ETF'],
            '주거': ['아파트', '전세', '청약', '대출', '리모델링', '내집마련'],
            '건강・의료': ['건강검진', '암검진', '갱년기', '고혈압', '당뇨', '입원', '수술', '헬스', '다이어트'],
            '육아・가족': ['어린이집', '육아', '맞벌이', '손주', '결혼', '워라밸'],
            '교육': ['입시', '수능', '학원', '교육비', '대학등록금'],
            '요양': ['요양', '주간보호', '방문', '케어', '요양원', '치매', '장기요양'],
            '웰다잉': ['웰다잉', '유언', '장례', '상속', '증여', '임종', '호스피스'],
            '라이프': ['취미', '여행', '봉사', '시니어'],
            '소통': ['디스코드', '카카오톡', 'MBTI', 'MZ세대']
        }
    }

    cat_dict = categories.get(country, categories['jp'])
    for cat, keywords in cat_dict.items():
        if any(k.lower() in keyword.lower() or keyword.lower() in k.lower() for k in keywords):
            return cat
    return 'その他' if country == 'jp' else '기타'


def fetch_url(url, headers=None, timeout=30):
    """URLからデータを取得"""
    if headers is None:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_context) as response:
            return response.read().decode('utf-8', errors='ignore')
    except Exception as e:
        print(f"  [WARN] Fetch failed: {url[:50]}... - {e}")
        return None


def fetch_news(keyword, hl, gl):
    """Google Newsから記事数を取得（週別分割で3か月分、最大1200件取得可能）"""
    total = 0
    recent = 0
    now = datetime.now()

    # 12週間分を週別に取得（各週最大100件 = 合計最大1200件）
    for week in range(12):
        # after:YYYY-MM-DD before:YYYY-MM-DD 形式で期間指定
        end_date = now - timedelta(days=week * 7)
        start_date = end_date - timedelta(days=7)

        after_str = start_date.strftime('%Y-%m-%d')
        before_str = end_date.strftime('%Y-%m-%d')

        # クエリ全体をURLエンコード（スペースも含めて）
        query = f"{keyword} after:{after_str} before:{before_str}"
        encoded_query = urllib.parse.quote(query)
        url = f"https://news.google.com/rss/search?q={encoded_query}&hl={hl}&gl={gl}&ceid={gl}:{hl}"

        text = fetch_url(url)
        if not text:
            continue

        week_count = len(re.findall(r'<item>', text))
        total += week_count

        # 直近7日（week=0）の記事数をカウント
        if week == 0:
            recent = week_count

        # レート制限対策
        time.sleep(0.3)

    return {'count': total, 'recent': recent}


def fetch_youtube(keyword, gl):
    """YouTube検索結果数と再生回数を取得"""
    url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}&gl={gl}"
    text = fetch_url(url)
    if not text:
        return {'count': 0, 'views': 0}

    count = len(re.findall(r'"videoRenderer"', text))

    # 再生回数を抽出
    view_matches = re.findall(r'"viewCountText":\{"simpleText":"([\d,万億]+)', text)
    total_views = 0
    for m in view_matches[:10]:  # 上位10件
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


def fetch_wikipedia(keyword, lang, days=90):
    """Wikipedia閲覧数を取得（複数日合計）"""
    article = urllib.parse.quote(keyword.replace(' ', '_'))
    end = datetime.now() - timedelta(days=1)
    start = end - timedelta(days=days-1)

    start_str = start.strftime('%Y%m%d')
    end_str = end.strftime('%Y%m%d')

    url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/per-article/{lang}.wikipedia/all-access/all-agents/{article}/daily/{start_str}/{end_str}"
    headers = {'User-Agent': 'TrendCollector/7.0 (https://github.com)'}

    text = fetch_url(url, headers)
    if not text:
        return 0

    try:
        data = json.loads(text)
        return sum(item.get('views', 0) for item in data.get('items', []))
    except:
        return 0


def analyze_keyword(keyword, country):
    """キーワードを分析"""
    hl = 'ja' if country == 'jp' else 'ko'
    gl = 'JP' if country == 'jp' else 'KR'
    lang = 'ja' if country == 'jp' else 'ko'

    # データ取得
    news_data = fetch_news(keyword, hl, gl)
    yt_data = fetch_youtube(keyword, gl)
    wiki = fetch_wikipedia(keyword, lang)

    news = news_data['count']
    news_recent = news_data['recent']
    yt = yt_data['count']
    yt_views = yt_data['views']

    # 総参照数
    total_refs = news + yt + wiki + (yt_views // 1000)

    # スコア計算
    news_score = min(30, news_recent * 1.5 + news * 0.1)
    yt_score = min(25, yt * 0.5 + min(15, yt_views / 100000))
    wiki_score = min(25, wiki / 400)

    total_score = news_score + yt_score + wiki_score
    category = categorize_keyword(keyword, country)

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


def save_to_kv(country, gen, keywords_data):
    """Cloudflare KVにデータを保存"""
    key = f"gen7_data_{country}_{gen}"
    value = json.dumps({
        'country': country,
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
    print("世代別トレンドデータ収集開始")
    print(f"実行時刻: {datetime.now().isoformat()}")
    print("=" * 60)

    if not all([CF_API_TOKEN, CF_ACCOUNT_ID, CF_KV_NAMESPACE_ID]):
        print("[ERROR] 環境変数が設定されていません")
        print(f"  CF_API_TOKEN: {'設定済み' if CF_API_TOKEN else '未設定'}")
        print(f"  CF_ACCOUNT_ID: {'設定済み' if CF_ACCOUNT_ID else '未設定'}")
        print(f"  CF_KV_NAMESPACE_ID: {'設定済み' if CF_KV_NAMESPACE_ID else '未設定'}")
        return

    for country in ['jp', 'kr']:
        print(f"\n{'='*40}")
        print(f"国: {'日本' if country == 'jp' else '韓国'}")
        print('='*40)

        for gen, keywords in KEYWORDS[country].items():
            print(f"\n[{gen}] {len(keywords)}キーワード分析中...")

            results = []
            for i, kw in enumerate(keywords):
                print(f"  [{i+1}/{len(keywords)}] {kw}...", end=' ')
                try:
                    result = analyze_keyword(kw, country)
                    results.append(result)
                    print(f"✓ score={result['score']}, refs={result['totalRefs']}")
                except Exception as e:
                    print(f"✗ {e}")

                # レート制限対策
                time.sleep(0.5)

            # ソートしてKVに保存
            results.sort(key=lambda x: x['score'], reverse=True)

            print(f"\n  KVに保存中...", end=' ')
            if save_to_kv(country, gen, results):
                print(f"✓ {len(results)}件保存完了")
            else:
                print("✗ 保存失敗")

    print("\n" + "=" * 60)
    print("データ収集完了")
    print("=" * 60)


if __name__ == '__main__':
    main()
