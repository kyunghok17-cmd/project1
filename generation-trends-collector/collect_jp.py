#!/usr/bin/env python3
"""
日本向け世代別トレンドデータ収集スクリプト
GitHub Actionsで毎日実行し、Cloudflare KVに保存

機能:
1. 過去キーワードの継承（KVから取得）
2. 複数ソースからの新規キーワード取得（Google Trends、はてブ、Yahoo!ニュース等）
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
OTHER_CATEGORY_THRESHOLD = 5  # 「その他」がこの数を超えたら新カテゴリを検討
MIN_CATEGORY_KEYWORDS = 2  # この数未満のカテゴリは統合候補
AUTO_CATEGORY_MIN_KEYWORDS = 3  # 自動カテゴリ生成に必要な最小キーワード数

# シードキーワード（初回実行時または前回データが少ない場合に使用）
SEED_KEYWORDS = {
    'genz': ['TikTok', 'VTuber', '原神', 'Apex Legends', 'YOASOBI', 'Ado', 'ChatGPT', 'MBTI', 'メルカリ', '推し活'],
    'millennial': ['NISA', '転職', 'ふるさと納税', '住宅ローン', '育児', 'Netflix', '副業', 'iDeCo', 'コストコ', 'ピラティス'],
    'genx': ['中学受験', '介護保険', '更年期', '年金', '相続', '大学受験', '人間ドック', '教育費', '住宅ローン', '健康診断']
}

# ランダム探索プール（埋もれている可能性のあるキーワード）
# これらからランダムに選んで探索することで、高スコアキーワードを発掘
EXPLORE_POOL = {
    'genz': [
        # ゲーム
        '鉄拳8', 'ゼンレスゾーンゼロ', '学園アイドルマスター', 'ウマ娘', 'プロセカ', 'FGO',
        '崩壊スターレイル', 'アークナイツ', 'フォートナイト', 'マインクラフト', 'どうぶつの森',
        # 配信・SNS
        '葛葉', '叶', 'ぶいすぽ', 'すとぷり', 'キヨ', '加藤純一', 'もこう', 'HIKAKIN',
        '東海オンエア', 'Fischer\'s', 'なろ屋', 'しまむらmii',
        # 音楽・エンタメ
        'なにわ男子', 'Snow Man', 'SixTONES', 'King Gnu', 'Vaundy', 'imase', 'ヒゲダン',
        'Official髭男dism', 'tuki.', '藤井風', 'Mrs. GREEN APPLE', 'ずっと真夜中でいいのに',
        # ファッション・トレンド
        'Y2K', 'サンリオ', 'ちいかわ', 'すみっコぐらし', 'シーイン', 'Temu', 'おぱんちゅうさぎ',
        # 学習・キャリア
        'Notion', 'Webデザイン', '動画編集', 'Canva', '簿記', 'TOEIC', 'Python'
    ],
    'millennial': [
        # 投資・資産
        '新NISA', 'つみたてNISA', 'S&P500', 'オールカントリー', '高配当株', 'ETF',
        'クレカ積立', '楽天証券', 'SBI証券', 'マネックス', '米国株',
        # 副業・キャリア
        'せどり', 'ブログ副業', 'YouTube副業', 'Webライター', 'クラウドワークス', 'ランサーズ',
        # 生活・家族
        '食洗機', 'ドラム式洗濯機', 'ルンバ', 'ホットクック', '時短家電',
        'こどもちゃれんじ', 'スマイルゼミ', 'くもん', '早期教育',
        # 健康・美容
        'チョコザップ', 'エニタイム', 'ゴールドジム', 'オンラインヨガ', '16時間断食',
        'オートファジー', 'プロテイン', 'ケトジェニック', 'ダーマペン', '美容医療'
    ],
    'genx': [
        # 教育
        'サピックス', '日能研', '四谷大塚', '早稲田アカデミー', '東進', '河合塾', '駿台',
        'スタディサプリ', '共通テスト', 'AO入試', '推薦入試',
        # 健康・医療
        'PET検査', 'MRI', '胃カメラ', '大腸カメラ', '前立腺がん', '乳がん検診',
        '緑内障', '白内障手術', '老眼治療', 'ICL', 'LASIK',
        # 資産・相続
        '相続税', '生前贈与', '遺産分割', '家族信託', '成年後見', '不動産評価',
        '終身保険', '介護保険', '所得補償', 'リバースモーゲージ',
        # 介護
        '介護認定', '地域包括支援センター', '訪問介護', '訪問看護', 'デイケア'
    ]
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

# カテゴリ分類パターン（拡充版）
# 部分一致で判定するため、キーワードの一部が含まれていればマッチ
CATEGORY_PATTERNS = {
    'SNS・動画': [
        'TikTok', 'ティックトック', 'YouTube', 'ユーチューブ', 'Shorts', 'ショート',
        'BeReal', 'Instagram', 'インスタ', '配信', '切り抜き', 'VTuber', 'Vtuber', 'ブイチューバー',
        'ライブ配信', 'Threads', 'スレッズ', 'ストリーマー', 'にじさんじ', 'ホロライブ',
        'Discord', 'ディスコード', 'X ', 'Twitter', 'ツイッター', 'LINE', 'ライン',
        '葛葉', '叶', 'ぶいすぽ', 'すとぷり', 'キヨ', '加藤純一', 'もこう', 'HIKAKIN', 'ヒカキン',
        '東海オンエア', 'Fischer', 'チャンネル', '登録者', 'バズ', 'トレンド入り', 'SNS'
    ],
    'ゲーム': [
        '原神', 'ブルアカ', 'ブルーアーカイブ', 'Valorant', 'ヴァロラント', 'Apex', 'エーペックス',
        'ポケモン', 'ポケットモンスター', 'スプラ', 'スプラトゥーン', 'ゼルダ', 'FF', 'ファイナルファンタジー',
        'eスポーツ', 'esports', 'モンスト', 'スターレイル', 'ストリートファイター', 'スト6',
        'ゲーム', 'Switch', 'スイッチ', 'PS5', 'プレステ', 'Steam', 'スチーム', 'Xbox',
        '鉄拳', 'tekken', 'ウマ娘', 'プロセカ', 'FGO', 'Fate', '崩壊', 'アークナイツ',
        'フォートナイト', 'Fortnite', 'マイクラ', 'マインクラフト', 'Minecraft', 'どうぶつの森',
        '荒野行動', 'PUBG', 'DbD', 'Dead by', 'モンハン', 'モンスターハンター',
        'ドラクエ', 'ドラゴンクエスト', 'ペルソナ', 'アトラス', 'カプコン', 'スクエニ',
        '任天堂', 'Nintendo', 'ソニー', 'バンナム', 'セガ', 'コナミ', 'ガチャ', 'リセマラ',
        '学園アイドルマスター', '学マス', 'アイマス', 'ゼンレスゾーンゼロ', 'ZZZ'
    ],
    '音楽・エンタメ': [
        'YOASOBI', 'Ado', 'アド', 'ボカロ', 'ボーカロイド', 'Spotify', 'スポティファイ',
        '音楽', '歌手', '声優', 'アニメ', 'Netflix', 'ネトフリ', '映画', '米津', '玄師',
        '推し活', '推し', 'フェス', 'ライブ', 'Amazon Prime', 'Disney', 'ディズニー',
        'ドラマ', 'コンサート', 'ツアー', 'なにわ男子', 'Snow Man', 'SixTONES',
        'King Gnu', 'キングヌー', 'Vaundy', 'imase', 'ヒゲダン', '髭男', 'Official髭男dism',
        'tuki.', '藤井風', 'Mrs. GREEN APPLE', 'ミセス', 'ずとまよ', 'ずっと真夜中でいいのに',
        'BTS', 'BLACKPINK', 'NewJeans', 'ニュージーンズ', 'IVE', 'aespa', 'LE SSERAFIM',
        'K-POP', 'KPOP', 'アイドル', 'ジャニーズ', 'AKB', '乃木坂', '櫻坂', '日向坂',
        '漫画', 'マンガ', 'コミック', '週刊少年', 'ジャンプ', 'マガジン', 'サンデー',
        '鬼滅', '呪術', 'ワンピース', 'ONE PIECE', '進撃', 'チェンソーマン', 'スパイファミリー'
    ],
    'ショッピング・決済': [
        'メルカリ', 'PayPay', 'ペイペイ', '通販', 'フリマ', 'Amazon', 'アマゾン',
        '楽天', 'コストコ', 'SHEIN', 'シーイン', 'ユニクロ', 'UNIQLO', 'GU', 'ジーユー',
        'IKEA', 'イケア', 'Qoo10', 'キューテン', 'ポイ活', 'ポイント', 'クーポン', 'セール',
        'Temu', 'テム', 'AliExpress', 'アリエク', 'Yahoo!ショッピング', 'ヤフショ',
        'ふるさと納税', '無印', 'MUJI', 'ニトリ', 'ドンキ', 'ドン・キホーテ',
        '100均', 'ダイソー', 'セリア', 'キャンドゥ', '買い物', 'ショッピング', '福袋', '初売り'
    ],
    'キャリア・学び': [
        '転職', '副業', 'リモート', 'テレワーク', '在宅勤務', 'フリーランス', '就活', '就職',
        'インターン', 'プログラミング', 'AI', 'ChatGPT', 'Claude', 'Gemini', 'Copilot',
        '資格', 'MBA', 'リスキリング', 'キャリア', 'スキル', '起業', 'スタートアップ',
        '退職', '会社', 'ビジネス', '仕事', 'エンジニア', 'デザイナー', 'マーケティング',
        'Notion', 'ノーション', 'Webデザイン', '動画編集', 'Canva', '簿記', 'TOEIC', 'Python',
        '英会話', '英語学習', 'オンライン学習', 'Udemy', 'Coursera', '公務員', '国家試験'
    ],
    '資産・投資': [
        'NISA', 'ニーサ', 'つみたて', '積立', 'iDeCo', 'イデコ', '投資', '株', '株式',
        '退職金', '年金', '資産', '相続', 'FIRE', 'S&P500', 'オルカン', 'オールカントリー',
        '高配当', '配当金', '仮想通貨', 'ビットコイン', 'BTC', 'FX', '為替', 'ドル円',
        '新NISA', '証券', '楽天証券', 'SBI証券', 'マネックス', '投資信託', 'ETF', 'インデックス',
        '節税', '確定申告', '税金', '金利', '利回り', '複利', '不労所得', '資産形成', '貯金', '貯蓄'
    ],
    '住宅': [
        'マンション', '住宅ローン', 'ローン', 'リフォーム', '住み替え', '固定資産',
        '持ち家', '賃貸', '引っ越し', '引越し', '不動産', '物件', '新築', '中古', '戸建て',
        '分譲', '売却', '購入', '家賃', '敷金', '礼金', '仲介', 'マイホーム', '一軒家',
        '住宅', '団地', 'タワマン', 'タワーマンション', '注文住宅', '建売'
    ],
    '健康・医療': [
        '人間ドック', 'がん', '癌', '検診', '更年期', '老眼', '高血圧', '糖尿病', '糖尿',
        '入院', '手術', '白内障', 'ジム', 'ダイエット', 'メンタル', 'スキンケア', 'ピラティス',
        '睡眠', 'ウォーキング', '骨密度', 'メタボ', 'コレステロール', '血圧', 'リハビリ', '美容',
        '病院', '医者', '医師', 'クリニック', '薬', '処方', '症状', '治療', '予防',
        '健康', 'ヘルス', 'フィットネス', 'チョコザップ', 'chocoZAP', 'エニタイム', 'ゴールドジム',
        '断食', 'ファスティング', 'プロテイン', 'サプリ', 'ビタミン', '漢方', '整体', 'マッサージ',
        'ヨガ', '筋トレ', 'トレーニング', 'ランニング', 'ジョギング', 'ストレッチ',
        '脱毛', 'レーザー', '美容整形', '美容皮膚科', 'ボトックス', 'ヒアルロン酸'
    ],
    '育児・家族': [
        '保育園', '幼稚園', '育児', 'ワンオペ', '子育て', '孫', '習い事', 'ベビー', '赤ちゃん',
        'マタニティ', '幼児教育', '出産', '妊娠', '妊活', '不妊', '産後', '授乳', 'ミルク',
        '離乳食', 'おむつ', 'ベビーカー', 'チャイルドシート', 'ランドセル', '七五三',
        '入園', '入学', 'PTA', '学童', '児童', '家族', '結婚', '婚活', '夫婦', 'ママ', 'パパ',
        'こどもちゃれんじ', 'しまじろう', 'スマイルゼミ', 'くもん', '公文'
    ],
    '介護': [
        '介護', 'デイサービス', '訪問介護', '訪問看護', 'ケアマネ', 'ケアマネージャー',
        '老人ホーム', '特養', '特別養護', 'グループホーム', '認知症', 'ヘルパー', '福祉用具',
        'ショートステイ', 'サ高住', 'サービス付き高齢者', '要介護', '要支援', 'ケアプラン',
        '介護保険', '介護認定', '地域包括', '施設', '入所', '在宅介護', '老老介護', 'ヤングケアラー'
    ],
    '終活': [
        '終活', '遺言', '遺言書', 'エンディング', 'エンディングノート', '葬儀', '葬式', '告別式',
        '墓', 'お墓', '墓地', '霊園', '納骨', '看取り', 'ホスピス', '緩和ケア', '延命',
        '相続', '遺産', '生前整理', '断捨離', '終末期', '人生会議'
    ],
    'ライフスタイル': [
        'MBTI', 'タイパ', 'コスパ', 'カフェ', '旅行', '観光', 'ホテル', '温泉', '趣味',
        'マイナンバー', 'キャッシュレス', 'サブスク', 'ポッドキャスト', 'グルメ', 'レシピ', '料理',
        '外食', 'レストラン', 'ラーメン', 'スイーツ', 'カレー', '居酒屋', 'バー',
        'ペット', '犬', '猫', 'キャンプ', 'アウトドア', 'BBQ', '釣り', 'ゴルフ', 'テニス',
        'サウナ', 'スパ', 'リラックス', '推し', 'オタク', '聖地巡礼', 'コスプレ', 'コミケ',
        'DIY', 'ハンドメイド', '手作り', 'ガーデニング', '園芸', '読書', '映画鑑賞'
    ],
    '教育': [
        '中学受験', '高校受験', '大学受験', '受験', '塾', '予備校', '教育費', '学費',
        '学資保険', '進学', '奨学金', '偏差値', '合格', '入試', '模試', '過去問',
        'サピックス', 'SAPIX', '日能研', '四谷大塚', '早稲田アカデミー', '早稲アカ',
        '東進', '河合塾', '駿台', 'スタディサプリ', 'スタサプ', '共通テスト', 'センター',
        'AO入試', '推薦', '総合型選抜', '指定校', '医学部', '東大', '京大', '早慶',
        'MARCH', '関関同立', '国公立', '私立', '通信制', 'オンライン授業', '不登校'
    ],
    'ニュース・社会': [
        '選挙', '政治', '首相', '大臣', '国会', '法案', '条例', '裁判', '判決',
        '事件', '事故', '災害', '地震', '台風', '警報', '避難', '速報', 'ニュース',
        '経済', '景気', '物価', 'インフレ', '円安', '円高', '金融', '日銀', '株価',
        '企業', '決算', '業績', 'IPO', '上場', '買収', '合併', '倒産', 'リストラ'
    ],
    'スポーツ': [
        '野球', 'サッカー', 'バスケ', 'バレー', 'テニス', 'ゴルフ', '相撲', '格闘技',
        'オリンピック', 'ワールドカップ', 'W杯', '甲子園', 'プロ野球', 'Jリーグ', 'NBA',
        '大谷', 'イチロー', 'メジャー', 'MLB', '日本代表', '優勝', '勝利', '敗北'
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
    print("\n  [1/4] Google Trends (日本) から急上昇ワードを取得中...")

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
            print(f"    [WARN] Google Trends取得失敗: {e}")

    print(f"    → {len(trends)}件")
    return trends


def fetch_yahoo_realtime():
    """Yahoo!リアルタイム検索からトレンドを取得"""
    print("  [2/4] Yahoo!リアルタイム検索からトレンドを取得中...")

    trends = []

    try:
        yahoo_url = "https://search.yahoo.co.jp/realtime"
        text = fetch_url(yahoo_url, timeout=15)
        if text:
            # 複数のパターンで抽出を試みる
            patterns = [
                r'<a[^>]*class="[^"]*trend[^"]*"[^>]*>([^<]+)</a>',
                r'"trendWord":"([^"]+)"',
                r'class="[^"]*Trend[^"]*"[^>]*>([^<]+)<'
            ]
            for pattern in patterns:
                matches = re.findall(pattern, text)
                for trend in matches[:20]:
                    trend = trend.strip()
                    if trend and len(trend) > 1 and trend not in trends:
                        trends.append(trend)
    except Exception as e:
        print(f"    [WARN] Yahoo!リアルタイム取得失敗: {e}")

    print(f"    → {len(trends)}件")
    return trends


def fetch_hatena_hotentry():
    """はてなブックマーク ホットエントリーからキーワードを抽出"""
    print("  [3/4] はてなブックマーク ホットエントリーからキーワードを取得中...")

    keywords = []

    # カテゴリ別RSS
    categories = ['it', 'game', 'entertainment', 'life', 'economics']

    for category in categories:
        try:
            rss_url = f"https://b.hatena.ne.jp/hotentry/{category}.rss"
            text = fetch_url(rss_url, timeout=15)
            if text:
                # タイトルからキーワードを抽出
                titles = re.findall(r'<title>([^<]+)</title>', text)
                for title in titles[1:10]:  # 各カテゴリから10件
                    # タイトルを単語に分解し、キーワードらしいものを抽出
                    # 英単語やカタカナ語を優先
                    words = re.findall(r'[A-Za-z]{3,}|[ァ-ヶー]{3,}', title)
                    for word in words[:3]:
                        if word not in keywords and len(word) >= 3:
                            keywords.append(word)

            time.sleep(0.3)
        except Exception as e:
            print(f"    [WARN] はてブ({category})取得失敗: {e}")

    print(f"    → {len(keywords)}件")
    return keywords


def fetch_yahoo_news_keywords():
    """Yahoo!ニュース トピックスからキーワードを抽出"""
    print("  [4/4] Yahoo!ニュース トピックスからキーワードを取得中...")

    keywords = []

    # Yahoo!ニュース RSS
    rss_urls = [
        "https://news.yahoo.co.jp/rss/topics/it.xml",
        "https://news.yahoo.co.jp/rss/topics/entertainment.xml",
        "https://news.yahoo.co.jp/rss/topics/life.xml",
        "https://news.yahoo.co.jp/rss/topics/economy.xml"
    ]

    for rss_url in rss_urls:
        try:
            text = fetch_url(rss_url, timeout=15)
            if text:
                titles = re.findall(r'<title>([^<]+)</title>', text)
                for title in titles[1:15]:
                    # タイトルからキーワードを抽出
                    words = re.findall(r'[A-Za-z]{3,}|[ァ-ヶー]{3,}|[一-龠]{2,}', title)
                    for word in words[:2]:
                        if word not in keywords and len(word) >= 2:
                            # 除外ワード
                            if word not in ['ニュース', 'トピックス', '速報', '発表', '判明', '可能性']:
                                keywords.append(word)

            time.sleep(0.3)
        except Exception as e:
            print(f"    [WARN] Yahoo!ニュース取得失敗: {e}")

    print(f"    → {len(keywords)}件")
    return keywords


def fetch_all_trend_sources():
    """全てのトレンドソースからキーワードを収集"""
    all_trends = []
    seen = set()

    # 各ソースから取得
    sources = [
        fetch_google_trends_jp(),
        fetch_yahoo_realtime(),
        fetch_hatena_hotentry(),
        fetch_yahoo_news_keywords()
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

    # 最もスコアの高い世代を返す（同点の場合はgenzを優先）
    max_score = max(scores.values())
    if max_score > 0:
        for gen in ['genz', 'millennial', 'genx', 'boomer', 'senior']:
            if scores[gen] == max_score:
                return gen

    # マッチしない場合はgenzをデフォルトに（若年層のトレンドが多いため）
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
    return 'その他'


def extract_common_words(keywords):
    """キーワード群から共通する単語を抽出"""
    word_count = {}
    for kw in keywords:
        # 日本語の単語を抽出（カタカナ、漢字、英語）
        words = re.findall(r'[ァ-ヶー]{2,}|[一-龠]{2,}|[A-Za-z]{3,}', kw)
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
        words = re.findall(r'[ァ-ヶー]{2,}|[一-龠]{2,}|[A-Za-z]{3,}', first_kw)
        if words:
            return words[0]

    return None


def guess_category_by_pattern(keyword):
    """キーワードのパターンからカテゴリを推測"""
    # 人名・タレント関連のパターン
    celebrity_patterns = ['俳優', '女優', '芸人', 'タレント', 'アナウンサー', 'モデル', '歌手', 'アイドル', '監督', '作家', '芸能']
    # 地域・場所関連
    location_patterns = ['地方', '県', '市', '区', '町', '村', '駅', '空港', '国', '半島', '列島']
    # テクノロジー・企業関連
    tech_patterns = ['Google', 'Apple', 'Microsoft', 'Amazon', 'Meta', 'Facebook', 'OpenAI', 'Anthropic',
                     'React', 'Python', 'Java', 'API', 'SDK', 'HDMI', 'USB', 'Bluetooth', 'Wi-Fi', 'AI']

    keyword_lower = keyword.lower()

    for pattern in celebrity_patterns:
        if pattern.lower() in keyword_lower or keyword_lower in pattern.lower():
            return '芸能・有名人'

    for pattern in location_patterns:
        if pattern in keyword:  # 日本語はlower不要
            return '地域・場所'

    for pattern in tech_patterns:
        if pattern.lower() in keyword_lower or keyword_lower == pattern.lower():
            return 'テクノロジー'

    # 人名っぽいパターン（カタカナ + ひらがな/漢字の組み合わせ）
    if re.match(r'^[一-龠ぁ-んァ-ヶー]+$', keyword) and len(keyword) >= 3 and len(keyword) <= 6:
        # 漢字2-4文字は人名の可能性が高い
        kanji_only = re.sub(r'[^一-龠]', '', keyword)
        if 2 <= len(kanji_only) <= 4:
            return '芸能・有名人'

    return None


def analyze_category_health(results):
    """カテゴリの健全性を分析し、動的に調整"""
    global CATEGORY_PATTERNS

    # カテゴリ別にキーワードを集計
    category_keywords = {}
    other_keywords = []

    for r in results:
        cat = r.get('category', 'その他')
        kw = r.get('keyword', '')
        if cat == 'その他':
            other_keywords.append(kw)
        else:
            if cat not in category_keywords:
                category_keywords[cat] = []
            category_keywords[cat].append(kw)

    changes_made = []

    # 1. 「その他」が多すぎる場合 → カテゴリを推測して再分類
    if len(other_keywords) >= OTHER_CATEGORY_THRESHOLD:
        print(f"\n  [カテゴリ分析] 「その他」が{len(other_keywords)}件 - 再分類を試行...")

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
                changes_made.append(f"「{cat_name}」に{len(keywords)}件を分類")
                print(f"    → 「{cat_name}」に分類: {keywords[:5]}...")

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
                            changes_made.append(f"新カテゴリ「{new_cat_name}」を作成（{len(matching_keywords)}件）")
                            print(f"    → 新カテゴリ「{new_cat_name}」を作成: {matching_keywords[:5]}...")

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
        print(f"\n  [カテゴリ分析] 空のカテゴリ: {empty_categories}")
        # 空のカテゴリは保持（将来のキーワード用）だが、ログに記録

    if small_categories:
        print(f"  [カテゴリ分析] キーワードが少ないカテゴリ: {small_categories}")
        # 小さいカテゴリは「ライフスタイル」に統合を検討
        for cat, count in small_categories:
            if cat not in ['終活', '介護', '教育']:  # 重要カテゴリは維持
                keywords_to_merge = category_keywords.get(cat, [])
                if keywords_to_merge and 'ライフスタイル' in CATEGORY_PATTERNS:
                    # 統合先にパターンを追加
                    CATEGORY_PATTERNS['ライフスタイル'].extend(keywords_to_merge)
                    changes_made.append(f"「{cat}」({count}件)を「ライフスタイル」に統合")
                    print(f"    → 「{cat}」を「ライフスタイル」に統合")

                    # 対象キーワードのカテゴリを更新
                    for r in results:
                        if r.get('category', '') == cat:
                            r['category'] = 'ライフスタイル'

    return changes_made


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


def quick_score_check(keyword):
    """キーワードの簡易スコアチェック（高速版）
    新規キーワード候補のフィルタリングに使用"""
    # Google Newsの直近1週間のみチェック
    now = datetime.now()
    end_date = now
    start_date = end_date - timedelta(days=7)
    after_str = start_date.strftime('%Y-%m-%d')
    before_str = end_date.strftime('%Y-%m-%d')

    query = f"{keyword} after:{after_str} before:{before_str}"
    encoded_query = urllib.parse.quote(query)
    url = f"https://news.google.com/rss/search?q={encoded_query}&hl=ja&gl=JP&ceid=JP:ja"

    text = fetch_url(url, timeout=10)
    news_count = len(re.findall(r'<item>', text)) if text else 0

    # YouTubeの検索結果数のみチェック
    yt_url = f"https://www.youtube.com/results?search_query={urllib.parse.quote(keyword)}&gl=JP"
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
    print("日本向け世代別トレンドデータ収集開始（拡張トレンドモード）")
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
                        if quick >= 20:  # ニュース3件以上 or YouTube検索10件以上相当
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

        # カテゴリの動的管理（「その他」が多い場合に新カテゴリを自動生成）
        category_changes = analyze_category_health(results)
        if category_changes:
            print(f"  カテゴリ変更: {len(category_changes)}件")

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
    print("日本データ収集完了（拡張トレンドモード）")
    print("=" * 60)


if __name__ == '__main__':
    main()
