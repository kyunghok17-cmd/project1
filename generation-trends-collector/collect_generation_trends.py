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

# 世代別キーワード定義（3世代のみ：genz, millennial, genx）
# boomer, seniorは除外して処理時間を短縮
KEYWORDS = {
    'jp': {
        'genz': [
            # SNS・動画 (6)
            'TikTok', 'YouTube Shorts', 'VTuber', 'にじさんじ', 'ホロライブ', 'Discord',
            # ゲーム (6)
            '原神', 'ブルーアーカイブ', 'Valorant', 'Apex Legends', 'スプラトゥーン3', 'eスポーツ',
            # 音楽・エンタメ (5)
            'YOASOBI', 'Ado', 'Spotify', '推し活', 'Netflix',
            # ショッピング (4)
            'メルカリ', 'PayPay', 'SHEIN', 'ユニクロ',
            # キャリア・学び (4)
            'ChatGPT', 'AI', '就活', 'プログラミング学習',
            # ライフスタイル (3)
            'MBTI', 'タイパ', 'LINE'
        ],
        'millennial': [
            # 資産形成 (5)
            'NISA', 'iDeCo', '投資信託', 'FIRE', '株式投資',
            # キャリア (5)
            '転職', '副業', 'リモートワーク', 'フリーランス', 'リスキリング',
            # 住宅・生活 (5)
            'マンション購入', '住宅ローン', 'ふるさと納税', 'コストコ', 'ポイ活',
            # 育児 (4)
            '保育園', '育児休暇', '子育て支援', 'ワンオペ育児',
            # 健康・エンタメ (4)
            'ジム', 'ダイエット', 'Netflix', 'サブスク'
        ],
        'genx': [
            # 教育 (4)
            '中学受験', '大学受験', '塾', '教育費',
            # 健康 (4)
            '人間ドック', 'がん検診', '更年期', '健康診断',
            # 介護 (4)
            '親の介護', '介護保険', '介護施設', 'デイサービス',
            # キャリア・資産 (3)
            '早期退職', '退職金運用', '老後資金'
        ]
    },
    'kr': {
        'genz': [
            '틱톡', '유튜브 쇼츠', '인스타그램', '버튜버', '디스코드',
            '원신', '블루아카이브', '발로란트', '리그오브레전드', 'e스포츠',
            'K-POP', '아이돌', 'BTS', 'BLACKPINK', '뉴진스',
            '무신사', '올리브영', '카카오페이', '네이버페이',
            '카카오톡', 'MBTI', '갓생',
            '취준', '코딩', 'ChatGPT', 'AI'
        ],
        'millennial': [
            '주식투자', '부동산', '코인', '재테크', 'ETF',
            '이직', 'N잡러', '재택근무', '프리랜서', '창업',
            '아파트', '전세', '청약', '대출', '내집마련',
            '어린이집', '육아휴직', '육아', '워라밸',
            '헬스', '다이어트', '넷플릭스', '웹툰'
        ],
        'genx': [
            '입시', '수능', '학원', '교육비',
            '건강검진', '암검진', '갱년기', '성인병',
            '부모님돌봄', '요양보험', '간병', '요양원',
            '명퇴', '조기퇴직', '노후준비'
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

# カテゴリ分類（拡張版 - Worker同期版）
def categorize_keyword(keyword, country):
    categories = {
        'jp': {
            'SNS・動画': ['TikTok', 'YouTube', 'Shorts', 'BeReal', 'Instagram', '配信', '切り抜き', 'VTuber', 'ライブ', 'Threads', 'Bluesky', 'Twitch', 'ストリーマー', 'にじさんじ', 'ホロライブ', 'SHOWROOM', 'Mastodon', 'Snapchat', 'Pinterest', 'WeChat', 'WhatsApp', 'Telegram', 'Signal', 'リール', 'ストーリー', 'インフルエンサー', 'クリエイター', 'ぶいちゅーば', 'Vチューバー', '生配信', 'アーカイブ', 'コラボ配信', 'スパチャ', 'メンバーシップ', 'サブスク配信', 'ブルースカイ', 'スレッズ', 'ツイッター', 'エックス', 'ティックトック', 'インスタ', 'リツイート', 'いいね', 'フォロー', 'フォロワー', 'バズ', '拡散', 'トレンド', 'ハッシュタグ', 'タグ付け', 'シェア', 'DM', 'ダイレクトメッセージ'],
            'ゲーム': ['原神', 'ブルアカ', 'ブルーアーカイブ', 'Valorant', 'スト6', 'ストリートファイター6', 'ストリートファイター', 'ゲーム', 'Apex', 'ポケモン', 'スマブラ', 'スプラ', 'ゼルダ', 'FF', 'eスポーツ', 'モンスト', 'パズドラ', 'ウマ娘', 'プロセカ', 'あんスタ', 'エンドフィールド', 'Endfield', 'アークナイツ', 'Arknights', 'ソシャゲ', 'ガチャ', 'マイクラ', 'Minecraft', 'フォートナイト', 'Fortnite', 'PUBG', 'DbD', 'Dead by Daylight', '荒野行動', 'COD', 'オーバーウォッチ', 'Overwatch', 'LoL', 'マリオ', 'カービィ', 'どうぶつの森', 'あつ森', 'ファイアーエムブレム', 'ドラクエ', 'ドラゴンクエスト', 'モンハン', 'モンスターハンター', 'ペルソナ', 'テイルズ', 'ダークソウル', 'エルデンリング', 'スターレイル', '崩壊', 'miHoYo', 'HoYoverse', 'ニーア', 'NieR', 'バイオハザード', 'Nintendo', '任天堂', 'PlayStation', 'PS5', 'Xbox', 'Steam', 'Switch', 'ゲーミングPC', 'RTX', 'GPU', 'FPS', 'RPG', 'MMORPG', 'バトロワ', 'レトロゲーム', 'インディーゲーム', 'ゲーム実況', 'ホヨバース', 'ゼンレスゾーンゼロ', 'ZZZ', '鳴潮', 'Wuthering Waves', 'リングフィット', 'リングフィットアドベンチャー', 'Fit Boxing', 'スイッチスポーツ', 'ポケモンGO', 'ポケGO', 'ドラゴンボール', 'ワンピースオデッセイ', 'ナルト', 'NARUTO', 'ブリーチ', 'BLEACH', '遊戯王', 'デュエマ', 'ポケカ', 'ポケモンカード', 'MTG', 'シャドバ', 'シャドウバース', 'デュエルリンクス', 'グラブル', 'グランブルーファンタジー', 'FGO', 'Fate', 'ツイステ', 'シノアリス', 'リネージュ', 'ラグナロク', '黒い砂漠', 'PSO2', 'NGS', 'ブルプロ', 'ブループロトコル', 'アトリエ', 'ライザ', 'ソウルハッカーズ', 'ファイナルファンタジー', 'キングダムハーツ', 'KH', 'スクエニ', 'カプコン', 'バンナム', 'コナミ', 'セガ', 'コーエー', 'アトラス', 'フロム', 'FromSoftware', 'ロックスター', 'EA', 'Ubisoft', 'Blizzard', 'Riot', 'Epic Games'],
            '音楽・エンタメ': ['YOASOBI', 'Ado', 'ボカロ', 'Spotify', '音楽', '声優', 'アニメ', 'Netflix', '映画', '米津', 'King Gnu', 'Official髭男dism', 'Mrs. GREEN APPLE', 'Vaundy', 'imase', '推し活', 'フェス', 'ライブ', 'アイドル', 'K-POP', 'BTS', 'BLACKPINK', 'TWICE', 'NewJeans', 'aespa', 'IVE', 'LE SSERAFIM', 'Stray Kids', 'SEVENTEEN', 'ジャニーズ', 'Snow Man', 'SixTONES', 'なにわ男子', '乃木坂', '櫻坂', '日向坂', 'AKB', '坂道', 'LDH', 'EXILE', '三代目', 'BE:FIRST', 'JO1', 'INI', 'NiziU', 'XG', 'ヒップホップ', 'ラップ', 'DJ', 'EDM', 'クラシック', 'ジャズ', 'ロック', 'バンド', 'ギター', 'ピアノ', 'ドラム', 'ベース', 'DTM', '作曲', '歌ってみた', 'カバー', 'MV', 'PV', 'コンサート', 'ツアー', 'ドーム', 'アリーナ', 'フェスティバル', 'サマソニ', 'フジロック', 'ロッキン', 'CDJ', 'アニソン', '劇伴', 'サントラ', 'OST', '葬送のフリーレン', 'フリーレン', '呪術廻戦', '呪術', 'ワンピース', 'ONE PIECE', 'ダンジョン飯', '薬屋のひとりごと', '薬屋', '鬼滅の刃', '鬼滅', 'SPY×FAMILY', 'スパイファミリー', 'チェンソーマン', '推しの子', '進撃の巨人', '進撃', 'ハイキュー', 'ブルーロック', 'キングダム', '転スラ', 'リゼロ', 'このすば', '無職転生', '俺だけレベルアップ', 'ソードアートオンライン', 'SAO', '鑑定士', '最強', '異世界', '転生', 'なろう', 'ラノベ', 'ライトノベル', '漫画', 'マンガ', 'コミック', '週刊少年ジャンプ', 'ジャンプ', 'マガジン', 'サンデー', 'チャンピオン', '同人誌', 'コミケ', 'コミックマーケット', 'サンリオ', 'クロミ', 'マイメロ', 'シナモロール', 'ポムポムプリン', 'ハローキティ', 'キティ', 'ちいかわ', 'すみっコぐらし', 'すみっコ', 'リラックマ', 'カピバラさん', 'モルカー', 'ピカチュウ', 'イーブイ', 'ディズニー', 'ミッキー', 'ミニー', 'ジブリ', 'トトロ', '千と千尋', 'ポケットモンスター'],
            'ショッピング・決済': ['メルカリ', 'PayPay', '通販', 'フリマ', 'Amazon', '楽天', 'コストコ', 'SHEIN', 'ユニクロ', 'GU', 'IKEA', 'ヤフオク', 'ラクマ', 'Qoo10', 'ZOZOTOWN', 'BASE', 'STORES', 'Shopify', 'minne', 'Creema', 'ハンドメイド', 'メルペイ', 'LINE Pay', '楽天ペイ', 'd払い', 'au PAY', 'Suica', 'PASMO', 'iD', 'QUICPay', 'クレジットカード', 'デビットカード', 'プリペイド', 'ポイント', 'ポイ活', 'クーポン', 'セール', 'ブラックフライデー', 'プライムデー', '無印', 'MUJI', 'ニトリ', 'ダイソー', 'セリア', 'キャンドゥ', '100均', 'ドンキ', 'ドン・キホーテ', 'ロフト', 'ハンズ', '東急ハンズ', 'ビックカメラ', 'ヨドバシ', '家電量販店', 'アウトレット', 'デパ地下', '百貨店', 'ショッピングモール'],
            'キャリア・学び': ['転職', '副業', 'リモート', 'フリーランス', '就活', 'インターン', 'プログラミング', 'AI', 'ChatGPT', '資格', '起業', 'オンライン学習', 'オンライン', '学習', 'Notion', 'Canva', 'Figma', 'GitHub', 'Duolingo', 'スタートアップ', 'ベンチャー', 'MBA', 'ビジネススクール', 'TOEIC', 'TOEFL', 'IELTS', '英会話', '英語学習', '語学', '簿記', 'FP', 'ITパスポート', '基本情報', '応用情報', '宅建', '行政書士', '社労士', '中小企業診断士', '公認会計士', '税理士', '弁護士', '司法書士', 'Udemy', 'Coursera', 'Schoo', 'グロービス', 'コーディング', 'Web開発', 'アプリ開発', 'データサイエンス', '機械学習', 'ディープラーニング', 'Python', 'JavaScript', 'React', 'Vue', 'TypeScript', 'クラウド', 'AWS', 'GCP', 'Azure', 'Docker', 'Kubernetes', 'SaaS', 'DX', 'デジタル化', 'リスキリング', 'アップスキリング', 'キャリアチェンジ', 'セカンドキャリア', 'パラレルキャリア', '複業', 'ギグワーク', 'ノマド', 'コワーキング', 'シェアオフィス', 'テレワーク', '在宅勤務', 'ハイブリッドワーク', 'ワークライフバランス'],
            '資産・投資': ['NISA', 'iDeCo', '投資', '株', '退職金', '年金', '資産', '相続', 'FIRE', 'S&P500', 'オルカン', '高配当', 'インデックス', '投資信託', 'ETF', '債券', '国債', '社債', 'REIT', '不動産投資', 'FX', '外貨', 'ドル', 'ユーロ', '仮想通貨', '暗号資産', 'ビットコイン', 'イーサリアム', 'NFT', 'ブロックチェーン', 'デイトレ', 'スイング', '長期投資', '積立投資', 'ドルコスト平均法', '分散投資', 'ポートフォリオ', 'アセットアロケーション', 'リバランス', '配当', '優待', '株主優待', 'IPO', '新規上場', 'PER', 'PBR', 'ROE', 'テクニカル', 'ファンダメンタル', '証券口座', 'ネット証券', 'SBI', '楽天証券', 'マネックス', '松井', 'auカブコム', '老後資金', '教育資金', '住宅資金', '生活防衛資金', '緊急資金', '節税', 'ふるさと納税', '確定申告', '青色申告', '白色申告', 'e-Tax', 'マイナポータル'],
            '住宅': ['マンション', '住宅ローン', 'リフォーム', '住み替え', '固定資産', '持ち家', '空き家', '実家じまい', '不動産', '戸建て', '一軒家', '新築', '中古', '賃貸', '分譲', 'タワマン', 'タワーマンション', '低層マンション', 'ヴィンテージマンション', 'リノベーション', 'リノベ', 'DIY', '間取り', '内覧', 'モデルルーム', '住宅展示場', 'ハウスメーカー', '工務店', '設計事務所', '建築家', '注文住宅', '建売', 'フルリノベ', 'スケルトン', '断熱', '省エネ', 'ZEH', '太陽光', '蓄電池', 'オール電化', 'スマートホーム', 'IoT住宅', 'フラット35', '変動金利', '固定金利', '繰り上げ返済', '借り換え', '団信', '火災保険', '地震保険', '管理費', '修繕積立金', '固定資産税', '都市計画税', '登記', '登録免許税', '不動産取得税', '仲介手数料', '引っ越し', '単身赴任', '二拠点生活', 'デュアルライフ'],
            '健康・医療': ['人間ドック', 'がん', '検診', '更年期', '老眼', '高血圧', '糖尿病', '入院', '手術', '白内障', '膝痛', '腰痛', '肩こり', '頭痛', '不眠', '睡眠', '睡眠障害', '無呼吸', 'いびき', 'ストレス', 'うつ', 'メンタルヘルス', '心療内科', '精神科', 'カウンセリング', 'セラピー', 'マインドフルネス', '瞑想', 'ダイエット', '減量', '糖質制限', 'ケトジェニック', 'ファスティング', '断食', 'プロテイン', 'サプリメント', 'ビタミン', 'ミネラル', 'コラーゲン', 'グルコサミン', '青汁', '酵素', '乳酸菌', '腸活', '免疫', '抗酸化', 'アンチエイジング', '美容医療', '美容整形', 'ボトックス', 'ヒアルロン酸', '脱毛', 'AGA', '薄毛', 'ED', 'ピル', '生理', 'PMS', 'PMD', '婦人科', '産婦人科', '不妊治療', '妊活', '歯科', '矯正', 'インプラント', 'ホワイトニング', '眼科', 'レーシック', 'ICL', 'コンタクト', '整形外科', '接骨院', '整体', 'カイロ', '鍼灸', 'マッサージ', 'リラクゼーション', 'スポーツジム', 'フィットネス', 'パーソナルトレーニング', '筋トレ', 'ウェイト', '有酸素', 'ウォーキング', 'ジョギング', '水泳', 'プール'],
            '育児・家族': ['保育園', '育児', 'ワンオペ', '子育て', '孫', '結婚', '家族', '帰省', 'モンテッソーリ', 'STEAM教育', '中学受験', 'プレスクール', '療育', '幼稚園', 'こども園', '認可', '認可外', '待機児童', '保活', 'ベビーシッター', 'ファミサポ', '産休', '育休', '時短勤務', 'マタハラ', 'パタハラ', 'イクメン', '家事分担', '共働き', '専業主婦', 'ワーママ', 'パパ活', 'ママ活', 'ママ友', 'PTA', '学童', '放課後', '習い事', '塾', '公文', '学研', 'そろばん', 'ピアノ', 'スイミング', 'サッカー', '野球', 'バレエ', 'ダンス', '英会話', 'プログラミング教室', 'ロボット教室', '小学校', '中学校', '高校', '私立', '公立', '国立', '受験', '入試', '内申', '偏差値', '模試', '塾選び', '家庭教師', '通信教育', 'タブレット学習', '発達障害', 'ADHD', 'ASD', '自閉症', 'LD', '学習障害', '不登校', 'フリースクール', 'ホームスクール', '反抗期', '思春期', '進路', '進学', '就職'],
            '介護': ['介護', 'デイサービス', '訪問', 'ケアマネ', '老人ホーム', '特養', 'グループホーム', '認知症', 'ダブルケア', '介護うつ', 'ケアラー', '要介護', '要支援', '介護認定', '区分変更', '介護保険', 'ケアプラン', 'ケアマネジャー', 'ヘルパー', '介護福祉士', '社会福祉士', '訪問介護', '訪問看護', '訪問リハ', '通所介護', '通所リハ', 'ショートステイ', '小規模多機能', '看多機', '定期巡回', '夜間対応', '福祉用具', '車いす', '介護ベッド', '歩行器', 'ポータブルトイレ', '紙おむつ', 'バリアフリー', '手すり', 'スロープ', '住宅改修', '有料老人ホーム', 'サ高住', 'サービス付き高齢者住宅', '介護医療院', '老健', '療養型', 'ユニット型', '個室', '多床室', '入居金', '月額費用', '医療連携', '看取り', 'ターミナル', '緩和ケア', 'アルツハイマー', 'レビー小体', '脳血管性', '前頭側頭型', 'MCI', '軽度認知障害', '徘徊', '暴力', '妄想', 'せん妄', '嚥下', '誤嚥', '胃ろう', '経管栄養', '褥瘡', '床ずれ'],
            '終活': ['終活', '遺言', 'エンディング', '葬儀', '墓', '看取り', 'ホスピス', '成年後見', '遺産', '相続税', '贈与', '生前贈与', '暦年贈与', '相続時精算課税', '遺留分', '遺産分割', '公正証書', '自筆証書', '秘密証書', 'エンディングノート', '人生会議', 'ACP', 'リビングウィル', '延命治療', '尊厳死', '安楽死', '臓器提供', '献体', '家族葬', '直葬', '一日葬', '自然葬', '樹木葬', '海洋散骨', '宇宙葬', '永代供養', '納骨堂', '合葬墓', '墓じまい', '改葬', '仏壇', '位牌', '法要', '法事', '初七日', '四十九日', '一周忌', '三回忌', '香典', '香典返し', '喪服', '礼服', '遺影', '遺骨', '火葬', '荼毘', '戒名', '法名', '坊主', '僧侶', '寺', '神社', '教会', '断捨離', 'ミニマリスト', '生前整理', '遺品整理', 'デジタル遺品', 'デジタル終活', 'パスワード', '解約', '退会'],
            'ライフスタイル': ['ミニマリスト', 'SDGs', 'タイパ', 'コスパ', '趣味', '旅行', 'キャンプ', 'ゴルフ', 'サステナブル', 'サステナブルファッション', 'エモい', 'バズる', '映え', 'チル', 'ピラティス', 'ヨガ', 'ランニング', 'ワーケーション', 'ファッション', 'オーガニック', '無添加', 'ヴィーガン', 'ベジタリアン', 'グルテンフリー', 'ローフード', 'スーパーフード', 'エシカル', 'フェアトレード', 'アップサイクル', 'リユース', 'リサイクル', 'ゼロウェイスト', 'エコ', '環境', '地球温暖化', '脱炭素', 'カーボンニュートラル', 'EV', '電気自動車', 'ソーラー', '再生可能エネルギー', 'ZARA', 'H&M', 'GAP', 'BEAMS', 'UNITED ARROWS', 'SHIPS', 'nano・universe', 'URBAN RESEARCH', 'JOURNAL STANDARD', 'BEAUTY&YOUTH', 'アウトドア', 'THE NORTH FACE', 'patagonia', 'mont-bell', 'Coleman', 'Snow Peak', '登山', 'トレッキング', 'ハイキング', 'サイクリング', 'ロードバイク', 'クロスバイク', 'マウンテンバイク', 'サーフィン', 'スノボ', 'スキー', 'ダイビング', 'シュノーケリング', 'SUP', 'カヤック', '釣り', 'フィッシング', 'バーベキュー', 'BBQ', 'グランピング', '車中泊', 'バンライフ', 'DIY', '日曜大工', 'ガーデニング', '家庭菜園', '園芸', '観葉植物', '多肉植物', 'ペット', '犬', '猫', 'うさぎ', 'ハムスター', '爬虫類', '熱帯魚', 'アクアリウム'],
            'コミュニケーション': ['Discord', 'LINE', 'チャット', 'SNS', 'Twitter', 'X', 'MBTI', 'オープンチャット', 'Slack', 'Teams', 'Zoom', 'Google Meet', 'Webex', 'オンライン会議', 'ビデオ通話', 'テレカン', 'チャットボット', 'ChatGPT', 'Claude', 'Gemini', 'Copilot', 'AI秘書', 'AI翻訳', 'DeepL', 'Google翻訳', '音声入力', '文字起こし', '議事録', 'コミュニティ', 'オンラインサロン', 'ファンクラブ', 'メンバーシップ', 'サブスク', 'Patreon', 'FANBOX', 'note', 'メルマガ', 'ニュースレター', 'Substack', 'Medium', 'ブログ', 'WordPress', 'はてなブログ', 'Ameba', 'ポッドキャスト', 'Podcast', 'Voicy', 'stand.fm', 'Radiotalk', 'Spoon', 'ライブ配信', '投げ銭', 'ギフティング'],
            'デリバリー・移動': ['Uber Eats', '出前館', 'Wolt', 'タイムズカー', 'カーシェア', 'menu', 'foodpanda', 'DiDi Food', 'Chompy', 'デリバリー', 'テイクアウト', 'ピックアップ', 'モバイルオーダー', 'タクシー', 'GO', 'S.RIDE', '配車アプリ', 'ライドシェア', 'Uber', 'Lyft', 'シェアサイクル', 'LUUP', '電動キックボード', 'レンタカー', 'オリックス', 'トヨタレンタカー', 'ニッポンレンタカー', 'タイムズ', 'カレコ', 'dカーシェア', 'Anyca', '個人間カーシェア', 'MaaS', '新幹線', '飛行機', '高速バス', '夜行バス', 'LCC', 'Peach', 'ジェットスター', 'スカイマーク', 'エアドゥ', 'ソラシド', 'スターフライヤー', 'JAL', 'ANA', 'マイル', 'ポイント', '特典航空券'],
            'フード・グルメ': ['スタバ', 'スターバックス', 'Starbucks', 'ドトール', 'タリーズ', 'コメダ', 'コメダ珈琲', 'ブルーボトル', '星乃珈琲', 'サンマルク', 'エクセルシオール', 'ベローチェ', 'カフェ', 'コーヒー', '珈琲', 'ラテ', 'フラペチーノ', 'マック', 'マクドナルド', 'McDonald', 'モスバーガー', 'モス', 'ケンタッキー', 'KFC', 'ケンタ', 'サブウェイ', 'バーガーキング', 'ウェンディーズ', 'ファーストキッチン', 'ロッテリア', 'フレッシュネス', 'シェイクシャック', 'ファイブガイズ', '吉野家', '松屋', 'すき家', 'なか卯', 'かつや', 'てんや', '大戸屋', 'やよい軒', 'ガスト', 'ジョナサン', 'ロイヤルホスト', 'デニーズ', 'サイゼリヤ', 'サイゼ', 'びっくりドンキー', 'ココス', 'バーミヤン', '餃子の王将', '日高屋', '幸楽苑', '丸亀製麺', 'はなまるうどん', 'ゆで太郎', 'かっぱ寿司', 'スシロー', 'くら寿司', 'はま寿司', '魚べい', '銀のさら', '回転寿司', 'ラーメン', 'つけ麺', '二郎', '家系', '一蘭', '一風堂', '天下一品', '蒙古タンメン', '焼肉', 'カルビ', 'しゃぶしゃぶ', 'すき焼き', 'タピオカ', 'ボバ', 'コンビニスイーツ', 'セブン', 'ローソン', 'ファミマ', 'ミスド', 'ミスタードーナツ', 'クリスピークリーム', 'シュークリーム', 'ケーキ', 'パフェ', 'パンケーキ', 'ワッフル', 'クレープ', 'アイス', 'ジェラート', 'ハーゲンダッツ', 'サーティワン'],
            '動画配信': ['U-NEXT', 'Hulu', 'ABEMA', 'Kindle', 'Audible', 'Amazon Prime', 'Amazonプライム', 'プライムビデオ', 'Disney+', 'ディズニープラス', 'Apple TV+', 'HBO Max', 'Paramount+', 'Peacock', 'dアニメストア', 'アニメ放題', 'バンダイチャンネル', 'FOD', 'Paravi', 'TELASA', 'WOWOW', 'スカパー', 'dTV', 'Lemino', 'DAZN', 'スポーツ配信', 'TVer', 'NHKプラス', 'YouTube Premium', 'YouTube Music', 'Apple Music', 'Amazon Music', 'LINE MUSIC', 'AWA', 'Deezer', 'TIDAL', 'SoundCloud', '電子書籍', 'Kindle Unlimited', '楽天マガジン', 'dマガジン', 'ブック放題', 'コミックシーモア', 'めちゃコミ', 'LINEマンガ', 'ピッコマ', 'マンガBANG', 'ジャンプ+', 'マガポケ', 'サンデーうぇぶり', 'ヤンジャン', 'オーディオブック', 'audiobook.jp', 'himalaya']
        },
        'kr': {
            'SNS・동영상': ['틱톡', '유튜브', '쇼츠', '인스타', '스트리밍', '버튜버', '스레드', '블루스카이', '트위치', '아프리카TV', '치지직'],
            '게임': ['원신', '블루아카', '발로란트', '리그오브', '게임', '메이플', '던전앤파이터', '로스트아크', '리니지', '배틀그라운드'],
            '음악・엔터': ['K-POP', '아이돌', 'BTS', '넷플릭스', '영화', '뉴진스', '에스파', 'IVE', '르세라핌', '스테이씨'],
            '쇼핑': ['무신사', '올리브영', '쿠팡', '카카오페이'],
            '커리어': ['이직', 'N잡', '재택', '프리랜서', '취준', 'AI', '세컨드커리어', '정년준비'],
            '재테크': ['주식', '부동산', '코인', '재테크', '펀드', '연금', 'ETF', '배당주', 'ISA'],
            '주거': ['아파트', '전세', '청약', '대출', '리모델링'],
            '건강・의료': ['건강검진', '암검진', '갱년기', '고혈압', '당뇨', '입원', '무릎통증', '허리통증'],
            '육아・가족': ['어린이집', '육아', '맞벌이', '손주', '결혼'],
            '요양': ['요양', '주간보호', '방문', '케어', '요양원', '치매', '간병', '더블케어'],
            '웰다잉': ['웰다잉', '유언', '장례', '납골', '임종'],
            '라이프': ['취미', '여행', '캠핑', '골프', '워케이션'],
            '소통': ['디스코드', '카카오톡', 'SNS'],
            '배달・이동': ['쿠팡이츠', '배달의민족', '요기요', '카카오T', '쏘카']
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
    """Google Newsから記事数を取得（週別分割で12週間分、各週最大100件）"""
    total = 0
    recent = 0
    now = datetime.now()

    # 12週間分（3か月）を週別に取得（各週最大100件 = 合計最大1200件）
    for week in range(12):
        end_date = now - timedelta(days=week * 7)
        start_date = end_date - timedelta(days=7)

        after_str = start_date.strftime('%Y-%m-%d')
        before_str = end_date.strftime('%Y-%m-%d')

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
        time.sleep(0.2)

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

    # スコア計算（YouTubeの影響力をニュースと同等に調整）
    news_score = min(30, news_recent * 1.5 + news * 0.1)
    yt_score = min(30, yt * 1.5 + min(15, yt_views / 100000))  # 係数を0.5→1.5に、上限を25→30に
    wiki_score = min(20, wiki / 400)  # WikipediaはNews/YouTubeより少し低めに

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

                # レート制限対策（短縮）
                time.sleep(0.3)

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
