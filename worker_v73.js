export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const p = url.pathname;
    const q = k => url.searchParams.get(k);

    // データ取得API（GitHub Actionsから呼び出し）
    if (p === '/api/save-data') return await handleSaveData(request, env);

    // 表示用API
    if (p === '/api/generation') return await handleGeneration(env, q('country') || 'jp', q('gen') || 'genz', q('exclude') || '');
    if (p === '/api/summary') return await handleSummary(env, q('country') || 'jp');
    if (p === '/api/keyword') return await handleKeyword(env, q('country') || 'jp', q('gen') || '', q('kw') || '');
    if (p === '/api/definitions') return json(getGenerationMeta(q('country') || 'jp'));
    if (p === '/api/exclude') return await handleExclude(request, env, q('country') || 'jp');
    if (p === '/api/custom') return await handleCustomKeywords(request, env, q('country') || 'jp', q('gen') || 'genz');
    if (p === '/api/analyze-custom') return await handleAnalyzeCustom(env, q('country') || 'jp', q('gen') || 'genz', q('kw') || '', q('cat') || '');
    if (p === '/api/categories') return await handleGetCategories(q('country') || 'jp');

    // 手動分析（フォールバック）
    if (p === '/api/analyze') return await handleAnalyze(env, q('country') || 'jp', q('gen') || 'genz');

    // 自動トレンドAPI
    if (p === '/api/auto-trends') return await handleAutoTrends(env, q('country') || 'jp');

    return new Response(getHTML(), { headers: { 'Content-Type': 'text/html; charset=utf-8' } });
  }
};

const json = (d, s = 200) => new Response(JSON.stringify(d), {
  status: s, headers: { 'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*' }
});

function getGenerationMeta(country) {
  const jp = {
    genz: { name: 'Z世代', age: '10〜25歳', birth: '2001-2016', icon: '📱', color: '#FF6B6B' },
    millennial: { name: 'ミレニアル世代', age: '26〜40歳', birth: '1986-2000', icon: '💼', color: '#4ECDC4' },
    genx: { name: 'X世代', age: '41〜55歳', birth: '1971-1985', icon: '🏠', color: '#45B7D1' },
    boomer: { name: 'ベビーブーマー', age: '56〜70歳', birth: '1956-1970', icon: '📰', color: '#96CEB4' },
    senior: { name: 'シニア世代', age: '71歳以上', birth: '〜1955', icon: '🏥', color: '#DDA0DD' }
  };
  const kr = {
    genz: { name: 'Z세대', age: '10〜25세', birth: '2001-2016', icon: '📱', color: '#FF6B6B' },
    millennial: { name: '밀레니얼 세대', age: '26〜40세', birth: '1986-2000', icon: '💼', color: '#4ECDC4' },
    genx: { name: 'X세대', age: '41〜55세', birth: '1971-1985', icon: '🏠', color: '#45B7D1' },
    boomer: { name: '베이비부머', age: '56〜70세', birth: '1956-1970', icon: '📰', color: '#96CEB4' },
    senior: { name: '시니어 세대', age: '71세 이상', birth: '〜1955', icon: '🏥', color: '#DDA0DD' }
  };
  return country === 'jp' ? jp : kr;
}

// 除外キーワードを取得
async function getExcludeList(env, country) {
  const key = `gen7_exclude_${country}`;
  const data = await env.TRENDS_KV.get(key, 'json');
  return data?.keywords || [];
}

// ユーザー追加キーワードを取得
async function getCustomKeywords(env, country, gen) {
  const key = `gen7_custom_${country}_${gen}`;
  const data = await env.TRENDS_KV.get(key, 'json');
  return data?.keywords || [];
}

// 除外キーワードを設定/取得
async function handleExclude(request, env, country) {
  if (request.method === 'POST') {
    try {
      const data = await request.json();
      const key = `gen7_exclude_${country}`;
      await env.TRENDS_KV.put(key, JSON.stringify({
        keywords: data.keywords || [],
        updatedAt: new Date().toISOString()
      }));
      return json({ success: true, excluded: data.keywords });
    } catch (e) {
      return json({ error: e.message }, 500);
    }
  }
  // GET: 現在の除外リストを返す
  const excludeList = await getExcludeList(env, country);
  return json({ country, excludedKeywords: excludeList });
}

// ユーザー追加キーワードを設定/取得
async function handleCustomKeywords(request, env, country, gen) {
  if (request.method === 'POST') {
    try {
      const data = await request.json();
      const key = `gen7_custom_${country}_${gen}`;
      await env.TRENDS_KV.put(key, JSON.stringify({
        keywords: data.keywords || [],
        updatedAt: new Date().toISOString()
      }));
      return json({ success: true, customKeywords: data.keywords });
    } catch (e) {
      return json({ error: e.message }, 500);
    }
  }
  const customKeywords = await getCustomKeywords(env, country, gen);
  return json({ country, gen, customKeywords });
}

// GitHub Actionsからデータを保存
async function handleSaveData(request, env) {
  try {
    const data = await request.json();
    const { country, gen, keywords, analyzedAt } = data;

    if (!country || !gen || !keywords) {
      return json({ error: 'Missing required fields' }, 400);
    }

    const key = `gen7_data_${country}_${gen}`;
    await env.TRENDS_KV.put(key, JSON.stringify({
      country, gen, keywords, analyzedAt,
      savedAt: new Date().toISOString()
    }));

    return json({ success: true, saved: keywords.length });
  } catch (e) {
    return json({ error: e.message }, 500);
  }
}

// リアルタイムトレンドキーワードプール（除外補充用）- 各世代に適した多様なカテゴリ
const TREND_POOL = {
  jp: {
    genz: [
      // SNS・動画
      'TikTok', 'YouTube Shorts', 'BeReal', 'Threads', 'Discord',
      // ゲーム
      '原神', 'スターレイル', 'ブルアカ', 'Apex Legends', 'Valorant',
      // 音楽・エンタメ
      'Spotify', 'Netflix', 'アニメ放題', 'YOASOBI', 'Ado',
      // ショッピング
      'SHEIN', 'Qoo10', 'メルカリ', 'PayPay',
      // ライフスタイル
      '推し活', 'カフェ巡り', 'インスタ映え', 'サウナ'
    ],
    millennial: [
      // 資産・投資
      '新NISA', 'オルカン', 'S&P500', 'iDeCo', '高配当株',
      // キャリア
      '転職エージェント', 'リスキリング', '副業', 'フリーランス',
      // 育児・家族
      '保育園', '育休', 'ベビーカー', '知育',
      // 住宅
      '住宅ローン', 'マンション購入', 'リノベーション',
      // ライフスタイル
      'ふるさと納税', 'コストコ', 'ワークライフバランス'
    ],
    genx: [
      // 教育
      '中学受験', '高校受験', '塾選び', '教育費',
      // 住宅・ローン
      '住宅ローン借り換え', 'リフォーム', 'リノベーション',
      // 介護
      '親の介護', '介護保険', 'ケアマネージャー', '介護施設',
      // 資産形成
      '老後資金', '年金受給', '退職金運用',
      // 健康
      '人間ドック', '健康診断', 'メタボ対策'
    ],
    boomer: [
      // 年金・社会保障
      '年金繰り下げ', '在職老齢年金', '高額療養費', '医療費控除',
      // 健康・医療
      'かかりつけ医', '健康診断', 'がん検診', '認知症予防',
      // 終活
      '終活', 'エンディングノート', '相続対策', '遺言書',
      // ライフスタイル
      '趣味', '旅行', 'シニア割引', '孫育て'
    ],
    senior: [
      // 介護サービス
      'デイサービス', '訪問介護', 'ショートステイ', '介護認定',
      // 医療・健康
      'かかりつけ医', '訪問診療', '薬の管理', 'リハビリ',
      // 生活支援
      '宅配弁当', '見守りサービス', '買い物支援', '配食サービス',
      // 福祉用具
      '車いす', '歩行器', '介護ベッド', '手すり設置'
    ]
  },
  kr: {
    genz: [
      // SNS
      '틱톡', '인스타그램', '유튜브 쇼츠', '디스코드',
      // 게임
      '원신', '블루아카', '스타레일', '롤', '발로란트',
      // 음악・엔터
      '멜론', '넷플릭스', '뉴진스', 'BTS', '에스파',
      // 쇼핑
      '무신사', '쿠팡', '올리브영',
      // 라이프
      '카페', '맛집', '인스타감성'
    ],
    millennial: [
      // 재테크
      '미국주식', 'S&P500', 'ETF', 'ISA', '배당주',
      // 커리어
      '이직', '부업', '프리랜서', '재택근무',
      // 육아
      '어린이집', '육아휴직', '출산휴가',
      // 주거
      '청약', '전세', '아파트', '인테리어',
      // 라이프
      '여행', '호캉스', '캠핑'
    ],
    genx: [
      // 교육
      '수능', '학원비', '과외', '입시',
      // 주거
      '주담대', '대출', '재건축',
      // 요양
      '부모님케어', '요양', '간병', '치매',
      // 재테크
      '노후준비', '상속', '증여', '절세'
    ],
    boomer: [
      // 연금
      '국민연금', '퇴직연금', '기초연금',
      // 건강
      '건강검진', '혈압', '당뇨', '콜레스테롤',
      // 보험
      '실손보험', '암보험', '치매보험',
      // 라이프
      '여행', '취미', '손주'
    ],
    senior: [
      // 요양
      '요양등급', '장기요양', '주간보호', '요양원',
      // 건강
      '방문요양', '방문목욕', '재활',
      // 생활
      '돌봄서비스', '무료급식', '경로당',
      // 복지
      '노인복지관', '실버타운'
    ]
  }
};

// 固定表示キーワード数
const TARGET_KEYWORD_COUNT = 50;

// 自動トレンドデータを取得
async function getAutoTrends(env, country, genKey) {
  const key = `gen7_auto_trends_${country}`;
  const data = await env.TRENDS_KV.get(key, 'json');
  if (!data || !data.trends) return [];
  return data.trends[genKey] || [];
}

// KVからデータを取得して表示
async function handleGeneration(env, country, genKey, excludeParam) {
  const key = `gen7_data_${country}_${genKey}`;
  const data = await env.TRENDS_KV.get(key, 'json');

  if (!data) {
    return await handleAnalyze(env, country, genKey);
  }

  const meta = getGenerationMeta(country)[genKey];
  if (!meta) return json({ error: 'Invalid generation' }, 400);

  // 除外リストを取得
  const excludeList = await getExcludeList(env, country);
  const paramExclude = excludeParam ? excludeParam.split(',').map(s => s.trim()) : [];
  const allExclude = [...new Set([...excludeList, ...paramExclude])];

  // カスタムキーワードを取得（別枠で管理）
  const customKeywords = await getCustomKeywords(env, country, genKey);
  const filteredCustom = customKeywords.filter(ck =>
    !allExclude.some(ex => ck.keyword.toLowerCase().includes(ex.toLowerCase()))
  ).map(ck => ({ ...ck, isCustom: true }));

  // 自動トレンドを取得（別枠で管理）
  const autoTrends = await getAutoTrends(env, country, genKey);
  const filteredAutoTrends = autoTrends.filter(at =>
    !allExclude.some(ex => at.keyword.toLowerCase().includes(ex.toLowerCase()))
  ).map(at => ({ ...at, isAutoDetected: true }));

  // 元データをスコア順でソート
  const sortedOriginal = [...data.keywords].sort((a, b) => (b.score || 0) - (a.score || 0));

  // 除外キーワードをフィルタリング（メインキーワードのみ）
  let filteredKeywords = sortedOriginal.filter(kw =>
    !allExclude.some(ex => kw.keyword.toLowerCase().includes(ex.toLowerCase()) || ex.toLowerCase().includes(kw.keyword.toLowerCase()))
  );

  // メインキーワードは50件まで（カスタムは含めない）
  const existingKwNames = new Set(filteredKeywords.map(k => k.keyword.toLowerCase()));

  // キーワード数調整ロジック（メインのみ）
  const hl = country === 'jp' ? 'ja' : 'ko';
  const gl = country === 'jp' ? 'JP' : 'KR';
  let addedFromTrend = [];

  // 不足分をトレンドプールから補充（カスタムは別枠なので含めない）
  if (filteredKeywords.length < TARGET_KEYWORD_COUNT) {
    const pool = TREND_POOL[country]?.[genKey] || [];
    const needed = TARGET_KEYWORD_COUNT - filteredKeywords.length;
    let added = 0;

    for (const kw of pool) {
      if (added >= needed) break;
      const kwLower = kw.toLowerCase();
      if (!existingKwNames.has(kwLower) &&
          !allExclude.some(ex => kwLower.includes(ex.toLowerCase()) || ex.toLowerCase().includes(kwLower))) {
        const analyzed = await analyzeKeywordLite(kw, hl, gl, country);
        analyzed.isTrendFill = true;
        filteredKeywords.push(analyzed);
        existingKwNames.add(kwLower);
        addedFromTrend.push(kw);
        added++;
      }
    }
  }

  // メインキーワードは50件まで
  if (filteredKeywords.length > TARGET_KEYWORD_COUNT) {
    filteredKeywords.sort((a, b) => (b.score || 0) - (a.score || 0));
    filteredKeywords = filteredKeywords.slice(0, TARGET_KEYWORD_COUNT);
  }

  // スコア順でソート
  filteredKeywords.sort((a, b) => (b.score || 0) - (a.score || 0));

  // カテゴリ別に集計（メインキーワードのみ）
  const categoryMap = {};
  for (const kw of filteredKeywords) {
    const cat = kw.category || (country === 'jp' ? 'その他' : '기타');
    if (!categoryMap[cat]) {
      categoryMap[cat] = { keywords: [], totalScore: 0, totalRefs: 0 };
    }
    categoryMap[cat].keywords.push(kw);
    categoryMap[cat].totalScore += kw.score || 0;
    categoryMap[cat].totalRefs += kw.totalRefs || 0;
  }

  const categories = Object.entries(categoryMap)
    .map(([name, d]) => ({
      name,
      keywords: d.keywords.sort((a, b) => (b.score || 0) - (a.score || 0)),
      totalScore: Math.round(d.totalScore * 10) / 10,
      totalRefs: d.totalRefs,
      avgScore: d.keywords.length > 0 ? Math.round((d.totalScore / d.keywords.length) * 10) / 10 : 0
    }))
    .sort((a, b) => b.totalScore - a.totalScore);

  return json({
    key: genKey,
    ...meta,
    country,
    period: '3か月',
    analyzedAt: data.analyzedAt,
    dataSource: 'pre-collected',
    totalKeywords: filteredKeywords.length,
    targetCount: TARGET_KEYWORD_COUNT,
    originalKeywords: data.keywords.length,
    excludedCount: allExclude.length,
    excludedKeywords: allExclude,
    addedFromTrend: addedFromTrend.length,
    trendKeywords: addedFromTrend,
    totalRefs: filteredKeywords.reduce((sum, k) => sum + (k.totalRefs || 0), 0),
    categories,
    allKeywords: filteredKeywords,
    customKeywords: filteredCustom,  // 別枠で返す
    autoTrends: filteredAutoTrends   // 自動検出トレンド（別枠）
  });
}

// 全世代サマリー
async function handleSummary(env, country) {
  const metas = getGenerationMeta(country);
  const result = { country, period: '3か月', analyzedAt: new Date().toISOString(), generations: [], totalRefs: 0 };

  for (const [genKey, meta] of Object.entries(metas)) {
    const key = `gen7_data_${country}_${genKey}`;
    const data = await env.TRENDS_KV.get(key, 'json');

    if (data && data.keywords) {
      const topKeywords = [...data.keywords]
        .sort((a, b) => (b.score || 0) - (a.score || 0))
        .slice(0, 3)
        .map(k => ({ keyword: k.keyword, score: k.score }));

      const totalScore = data.keywords.reduce((sum, k) => sum + (k.score || 0), 0);
      const totalRefs = data.keywords.reduce((sum, k) => sum + (k.totalRefs || 0), 0);

      result.generations.push({
        key: genKey,
        ...meta,
        topKeywords,
        totalScore: Math.round(totalScore * 10) / 10,
        totalRefs,
        keywordCount: data.keywords.length,
        analyzedAt: data.analyzedAt
      });
      result.totalRefs += totalRefs;
    } else {
      result.generations.push({
        key: genKey,
        ...meta,
        topKeywords: [],
        totalScore: 0,
        totalRefs: 0,
        keywordCount: 0,
        analyzedAt: null,
        noData: true
      });
    }
  }

  return json(result);
}

// 個別キーワード詳細（カスタム/トレンドキーワードも検索）
async function handleKeyword(env, country, genKey, keyword) {
  if (!keyword) return json({ error: 'keyword required' }, 400);

  const meta = getGenerationMeta(country)[genKey] || {};

  // 1. まずKVの事前収集データから検索
  const key = `gen7_data_${country}_${genKey}`;
  const data = await env.TRENDS_KV.get(key, 'json');

  if (data && data.keywords) {
    const kw = data.keywords.find(k => k.keyword === keyword);
    if (kw) {
      const sameCategory = data.keywords
        .filter(k => k.category === kw.category && k.keyword !== keyword)
        .sort((a, b) => (b.score || 0) - (a.score || 0))
        .slice(0, 5);

      return json({
        ...kw,
        genKey,
        genName: meta.name || '',
        genIcon: meta.icon || '',
        color: meta.color || '#888',
        country,
        relatedKeywords: sameCategory
      });
    }
  }

  // 2. カスタムキーワードから検索
  const customKeywords = await getCustomKeywords(env, country, genKey);
  const customKw = customKeywords.find(k => k.keyword === keyword);
  if (customKw) {
    return json({
      ...customKw,
      genKey,
      genName: meta.name || '',
      genIcon: meta.icon || '',
      color: meta.color || '#888',
      country,
      isCustom: true,
      relatedKeywords: []
    });
  }

  // 3. トレンドプールから検索（リアルタイム分析）
  const pool = TREND_POOL[country]?.[genKey] || [];
  if (pool.includes(keyword)) {
    const hl = country === 'jp' ? 'ja' : 'ko';
    const gl = country === 'jp' ? 'JP' : 'KR';
    const analyzed = await analyzeKeywordLite(keyword, hl, gl, country);

    return json({
      ...analyzed,
      genKey,
      genName: meta.name || '',
      genIcon: meta.icon || '',
      color: meta.color || '#888',
      country,
      isTrendFill: true,
      isLite: true,
      relatedKeywords: []
    });
  }

  // 4. 見つからない場合はリアルタイム分析を実行
  const hl = country === 'jp' ? 'ja' : 'ko';
  const gl = country === 'jp' ? 'JP' : 'KR';
  const analyzed = await analyzeKeywordLite(keyword, hl, gl, country);

  return json({
    ...analyzed,
    genKey,
    genName: meta.name || '',
    genIcon: meta.icon || '',
    color: meta.color || '#888',
    country,
    isLite: true,
    relatedKeywords: []
  });
}

// リアルタイム分析が存在しない場合のフォールバック
async function handleAnalyze(env, country, genKey) {
  const meta = getGenerationMeta(country)[genKey];
  if (!meta) return json({ error: 'Invalid generation' }, 400);

  return json({
    key: genKey,
    ...meta,
    country,
    period: '3か月',
    dataSource: 'none',
    totalKeywords: 0,
    totalRefs: 0,
    categories: [],
    allKeywords: [],
    notice: 'データがまだ収集されていません。GitHub Actionsによる次回の収集をお待ちください。'
  });
}

// キーワードを世代・国に基づいてカテゴリ分類（強化版）
function categorizeKeyword(keyword, country) {
  const kw = keyword.toLowerCase();

  if (country === 'jp') {
    // ゲーム
    if (/原神|スターレイル|ブルアカ|ゼンレスゾーンゼロ|鳴潮|パルワールド|ウマ娘|ff|ドラクエ|ポケモン|apex|valorant|lol|スプラ|マリオ|ゼルダ|モンハン|エルデン|プロセカ|fgo|グラブル|にじさんじ|ホロライブ|vtuber|ゲーム|ガチャ|ソシャゲ|eスポーツ|steam|nintendo|プレステ|switch/i.test(keyword)) return 'ゲーム';

    // SNS・動画
    if (/tiktok|youtube|instagram|twitter|x|line|discord|bereal|threads|ショート|リール|ストーリー|sns|インスタ|ツイッター/i.test(keyword)) return 'SNS・動画';

    // 音楽・エンタメ
    if (/spotify|apple music|サブスク|ライブ|フェス|コンサート|アニメ|映画|netflix|アマプラ|disney|yoasobi|ado|アーティスト|音楽|ドラマ|テレビ|放送/i.test(keyword)) return '音楽・エンタメ';

    // ショッピング・決済
    if (/paypay|メルカリ|shein|qoo10|amazon|楽天|zozotown|クレカ|決済|qr|タッチ決済|ショッピング|通販|セール|ポイ活|コストコ/i.test(keyword)) return 'ショッピング・決済';

    // キャリア・学び
    if (/転職|副業|フリーランス|リモート|プログラミング|ai|chatgpt|スキルアップ|資格|toeic|リスキリング|udemy|キャリア|就職|エージェント|ワークライフ/i.test(keyword)) return 'キャリア・学び';

    // 資産・投資
    if (/nisa|ideco|投資|etf|株|仮想通貨|fx|貯金|節約|オルカン|s&p|配当|証券|ふるさと納税|資産|運用/i.test(keyword)) return '資産・投資';

    // 住宅
    if (/住宅ローン|マンション|戸建て|リフォーム|賃貸|引越し|インテリア|リノベ|借り換え|不動産/i.test(keyword)) return '住宅';

    // 健康・医療
    if (/ジム|フィットネス|ダイエット|筋トレ|ヨガ|メンタル|睡眠|サプリ|健康診断|病院|人間ドック|がん検診|かかりつけ|メタボ|サウナ|医療|予防/i.test(keyword)) return '健康・医療';

    // 育児・家族
    if (/妊娠|出産|育休|保育園|幼稚園|ベビー|子育て|ママ|パパ|知育|ベビーカー|離乳食|育児/i.test(keyword)) return '育児・家族';

    // 教育
    if (/中学受験|高校受験|大学受験|塾|習い事|学費|奨学金|教育費|入試|偏差値|進学/i.test(keyword)) return '教育';

    // 介護
    if (/介護|認知症|デイサービス|ヘルパー|要介護|ケアマネ|訪問看護|在宅介護|特養|老健|グループホーム|施設|要支援|ショートステイ|福祉用具|車いす|歩行器/i.test(keyword)) return '介護';

    // 終活・相続
    if (/終活|相続|遺言|墓|葬儀|エンディング|遺産|贈与|生前/i.test(keyword)) return '終活・相続';

    // 年金・社会保障
    if (/年金|老齢|遺族年金|厚生年金|国民年金|繰り下げ|高額療養費|医療費控除|社会保障/i.test(keyword)) return '年金・社会保障';

    // ライフスタイル
    if (/カフェ|グルメ|旅行|ホテル|キャンプ|趣味|ペット|推し活|映え|巡り|サウナ|温泉/i.test(keyword)) return 'ライフスタイル';
  } else {
    // 韓国語カテゴリ
    if (/원신|블루아카|스타레일|로스트아크|메이플|배그|롤|발로란트|피파|던파|게임|젠레스|명조/i.test(keyword)) return '게임';
    if (/유튜브|틱톡|인스타|트위터|카카오톡|네이버|라인|sns|쇼츠|디스코드/i.test(keyword)) return 'SNS・동영상';
    if (/멜론|스포티파이|아이돌|k-pop|콘서트|넷플릭스|왓챠|bts|뉴진스|에스파|ive|음악/i.test(keyword)) return '음악・엔터';
    if (/쿠팡|무신사|올리브영|마켓컬리|배민|당근마켓|쇼핑/i.test(keyword)) return '쇼핑';
    if (/이직|취업|부업|프리랜서|스펙|자격증|재택|커리어/i.test(keyword)) return '커리어';
    if (/주식|코인|부동산|적금|펀드|etf|isa|배당|투자|s&p/i.test(keyword)) return '재테크';
    if (/전세|월세|청약|아파트|빌라|인테리어|주담대|대출/i.test(keyword)) return '주거';
    if (/헬스|다이어트|필라테스|영양제|병원|건강검진/i.test(keyword)) return '건강・의료';
    if (/임신|출산|육아휴직|어린이집|유치원|육아/i.test(keyword)) return '육아・가족';
    if (/수능|학원|과외|유학|영어|입시|교육/i.test(keyword)) return '교육';
    if (/요양|간병|치매|노인복지|장기요양|돌봄/i.test(keyword)) return '요양';
    if (/상속|유언|장례|보험|연금/i.test(keyword)) return '연금・보험';
    if (/카페|맛집|여행|호캉스|캠핑/i.test(keyword)) return '라이프';
  }

  return country === 'jp' ? 'その他' : '기타';
}

// 改善版リアルタイム分析（YouTube影響力強化）
async function analyzeKeywordLite(kw, hl, gl, country) {
  const lang = hl === 'ja' ? 'ja' : 'ko';

  // API呼び出し
  let news = 0, yt = 0, ytQuality = 0;

  // 1. Google News（7日間）
  try {
    const newsRes = await fetch(`https://news.google.com/rss/search?q=${encodeURIComponent(kw)}+when:7d&hl=${hl}&gl=${gl}`, { headers: { 'User-Agent': 'Mozilla/5.0' } });
    if (newsRes.ok) {
      const newsText = await newsRes.text();
      news = (newsText.match(/<item>/g) || []).length;
    }
  } catch {}

  // 2. YouTube検索（動画数 + 品質評価）
  try {
    const ytRes = await fetch(`https://www.youtube.com/results?search_query=${encodeURIComponent(kw)}&gl=${gl}`, {
      headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' }
    });
    if (ytRes.ok) {
      const ytText = await ytRes.text();
      // 動画数をカウント
      yt = (ytText.match(/"videoRenderer"/g) || []).length;

      // 品質指標：
      // - 「万回視聴」「万 回視聴」が多いほど高品質（人気コンテンツ）
      const viewsHigh = (ytText.match(/\d+万.*?回視聴/g) || []).length;
      // - 「公式」「Official」チャンネルが多いほど認知度高い
      const official = (ytText.match(/公式|Official|OFFICIAL/gi) || []).length;
      // - 最近の投稿が多い（「日前」「時間前」「分前」）
      const recent = (ytText.match(/\d+\s*(日前|時間前|分前)/g) || []).length;

      // 品質スコア（0-15点追加）
      ytQuality = Math.min(15, viewsHigh * 2 + official * 1.5 + recent * 0.5);
    }
  } catch {}

  // スコア計算（改善版）
  // ニュース: 最大30点（news * 2、7日間のホットニュース重視）
  // YouTube基本: 最大25点（動画の存在数）
  // YouTube品質: 最大15点（人気度・公式・最新）
  // 合計: 最大70点

  const newsScore = Math.min(30, news * 2);
  const ytBaseScore = Math.min(25, yt * 1.2);
  const ytQualityScore = Math.min(15, ytQuality);
  const totalYtScore = ytBaseScore + ytQualityScore;
  const score = newsScore + totalYtScore;

  return {
    keyword: kw,
    category: categorizeKeyword(kw, country),
    score: Math.round(score * 10) / 10,
    totalRefs: news + yt,
    news,
    yt,
    ytQuality: Math.round(ytQuality * 10) / 10,
    wiki: 0,
    newsRecent: news,
    isCustom: false,
    isLite: true
  };
}

// カテゴリリストを取得
function getCategoryList(country) {
  return country === 'jp' ?
    ['SNS・動画', 'ゲーム', '音楽・エンタメ', 'ショッピング・決済', 'キャリア・学び', '資産・投資', '住宅', '健康・医療', '育児・家族', '教育', '介護', '終活', 'ライフスタイル', 'コミュニケーション', 'シニア生活', 'デリバリー・移動', '動画配信', 'その他'] :
    ['SNS・동영상', '게임', '음악・엔터', '쇼핑', '커리어', '재테크', '주거', '건강・의료', '육아・가족', '교육', '요양', '웰다잉', '라이프', '소통', '배달・이동', '기타'];
}

// カスタムキーワードを分析
async function handleAnalyzeCustom(env, country, gen, keyword, category) {
  if (!keyword) return json({ error: 'keyword required' }, 400);

  const hl = country === 'jp' ? 'ja' : 'ko';
  const gl = country === 'jp' ? 'JP' : 'KR';

  const result = await analyzeKeywordLite(keyword, hl, gl, country);
  result.isCustom = true;

  // カテゴリが指定されていれば上書き、なければ自動分類を使用
  if (category && category !== '') {
    result.category = category;
  }

  // カスタムキーワードリストに追加
  const customKey = `gen7_custom_${country}_${gen}`;
  const existingData = await env.TRENDS_KV.get(customKey, 'json');
  const existingKeywords = existingData?.keywords || [];

  // 重複チェック
  const exists = existingKeywords.some(k => k.keyword === keyword);
  if (!exists) {
    existingKeywords.push(result);
    await env.TRENDS_KV.put(customKey, JSON.stringify({
      keywords: existingKeywords,
      updatedAt: new Date().toISOString()
    }));
  }

  return json({ success: true, result, added: !exists, categories: getCategoryList(country) });
}

// カテゴリリストAPI
async function handleGetCategories(country) {
  return json({ categories: getCategoryList(country) });
}

// 自動トレンド取得API
async function handleAutoTrends(env, country) {
  const key = `gen7_auto_trends_${country}`;
  const data = await env.TRENDS_KV.get(key, 'json');

  if (!data) {
    return json({
      country,
      trends: {},
      detectedAt: null,
      message: '自動トレンドデータがまだ収集されていません'
    });
  }

  return json({
    country,
    trends: data.trends || {},
    detectedAt: data.detectedAt,
    totalCount: Object.values(data.trends || {}).reduce((sum, arr) => sum + arr.length, 0)
  });
}

function getHTML() {
  return `<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>世代別トレンド v7</title><style>*{box-sizing:border-box;margin:0;padding:0}body{font-family:system-ui,sans-serif;background:linear-gradient(135deg,#1a1a2e,#16213e);color:#e0e0e0;min-height:100vh}.h{background:rgba(255,255,255,.03);padding:20px;text-align:center;border-bottom:1px solid rgba(255,255,255,.1)}.h h1{font-size:1.4rem;background:linear-gradient(90deg,#FF6B6B,#4ECDC4,#45B7D1,#96CEB4,#DDA0DD);-webkit-background-clip:text;-webkit-text-fill-color:transparent}.h p{color:#888;font-size:.75rem;margin-top:5px}.h .ver{color:#4ECDC4;font-size:.7rem;margin-top:8px}.h .info{display:flex;justify-content:center;gap:12px;margin-top:10px;font-size:.65rem;color:#666;flex-wrap:wrap}.h .info span{padding:3px 8px;background:rgba(255,255,255,.05);border-radius:4px}.c{display:flex;justify-content:center;gap:8px;padding:12px;background:rgba(0,0,0,.2)}.b{padding:8px 14px;border-radius:8px;border:1px solid rgba(255,255,255,.2);background:rgba(255,255,255,.05);color:#fff;font-size:.85rem;cursor:pointer}.b.a{background:rgba(78,205,196,.2);color:#4ECDC4;border-color:#4ECDC4}.m{max-width:1200px;margin:0 auto;padding:15px}.stats{display:flex;justify-content:center;gap:25px;margin-bottom:15px;padding:12px;background:rgba(255,255,255,.03);border-radius:10px;flex-wrap:wrap}.stats .stat{text-align:center;min-width:80px}.stats .stat .v{font-size:1.3rem;font-weight:700;color:#4ECDC4}.stats .stat .l{font-size:.65rem;color:#888}.gc{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:12px;margin-bottom:20px}.gcard{background:rgba(255,255,255,.03);border-radius:12px;padding:15px;border-top:4px solid;cursor:pointer;transition:all .2s}.gcard:hover{transform:translateY(-3px);background:rgba(255,255,255,.06)}.gcard.no-data{opacity:.5}.gcard .icon{font-size:2rem;margin-bottom:8px}.gcard .name{font-size:1rem;font-weight:600}.gcard .age{font-size:.75rem;color:#888;margin-top:2px}.gcard .top-kw{margin-top:10px;font-size:.7rem}.gcard .kw{display:inline-block;padding:2px 6px;background:rgba(255,255,255,.05);border-radius:4px;margin:2px;color:#aaa}.gcard .refs{font-size:.8rem;color:#FF6B6B;margin-top:8px}.gcard .cnt{font-size:.75rem;color:#4ECDC4;margin-top:4px}.gcard .no-data-msg{font-size:.7rem;color:#888;margin-top:10px}.detail{display:none}.detail.a{display:block}.dh{display:flex;align-items:center;gap:12px;padding:15px;background:rgba(255,255,255,.03);border-radius:12px;margin-bottom:15px;flex-wrap:wrap}.dh .icon{font-size:2.5rem}.dh .info{flex:1;min-width:200px}.dh .name{font-size:1.2rem;font-weight:600}.dh .sub{font-size:.8rem;color:#888}.dh .refs{font-size:.9rem;color:#FF6B6B;margin-top:4px}.dh .back{padding:8px 15px;background:rgba(255,255,255,.1);border:none;color:#fff;border-radius:8px;cursor:pointer}.cats{margin-bottom:20px}.cat{background:rgba(255,255,255,.03);border-radius:10px;margin-bottom:10px;overflow:hidden}.cat-h{padding:12px 15px;cursor:pointer;display:flex;align-items:center;gap:10px;border-left:4px solid}.cat-h:hover{background:rgba(255,255,255,.03)}.cat-h .cat-name{font-weight:600;flex:1}.cat-h .cat-score{font-size:.9rem;font-weight:700}.cat-h .cat-refs{font-size:.75rem;color:#FF6B6B;margin-left:10px}.cat-h .cat-cnt{font-size:.7rem;color:#888;margin-left:10px}.cat-h .arrow{transition:transform .2s}.cat.open .arrow{transform:rotate(90deg)}.cat-body{display:none;padding:0 15px 15px}.cat.open .cat-body{display:block}.kw-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:8px}.kw-card{background:rgba(0,0,0,.2);border-radius:8px;padding:10px;display:flex;align-items:center;gap:10px;cursor:pointer;transition:all .2s}.kw-card:hover{background:rgba(0,0,0,.3);transform:translateX(3px)}.kw-card .rank{font-size:1rem;font-weight:700;color:#4ECDC4;width:24px}.kw-card .kw-info{flex:1}.kw-card .kw-name{font-weight:600;font-size:.85rem}.kw-card .kw-metrics{display:flex;gap:8px;font-size:.6rem;color:#888;margin-top:3px}.kw-card .kw-score{font-size:1rem;font-weight:700}.kw-card .kw-refs{font-size:.65rem;color:#FF6B6B}.all-kw{margin-top:20px}.all-kw h3{font-size:.9rem;color:#888;margin-bottom:10px;padding-left:5px}.all-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:6px}.all-item{background:rgba(255,255,255,.02);border-radius:6px;padding:8px 10px;display:flex;justify-content:space-between;align-items:center;font-size:.75rem;cursor:pointer;transition:all .2s}.all-item:hover{background:rgba(255,255,255,.05)}.all-item .name{flex:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.all-item .cat{font-size:.6rem;color:#888;padding:2px 5px;background:rgba(255,255,255,.05);border-radius:3px;margin:0 6px;white-space:nowrap}.all-item .score{font-weight:600}.ld{text-align:center;padding:40px;color:#666}.sp{width:35px;height:35px;border:3px solid rgba(255,255,255,.1);border-top-color:#4ECDC4;border-radius:50%;animation:spin 1s linear infinite;margin:0 auto 10px}@keyframes spin{to{transform:rotate(360deg)}}.prog{width:200px;height:6px;background:rgba(255,255,255,.1);border-radius:3px;margin:15px auto 0;overflow:hidden}.prog-bar{height:100%;background:linear-gradient(90deg,#4ECDC4,#45B7D1);border-radius:3px;width:0%;transition:width .3s}.ld-msg{font-size:.75rem;color:#888;margin-top:10px}.ld-pct{font-size:1.2rem;font-weight:700;color:#4ECDC4;margin-top:8px}.md{display:none;position:fixed;top:0;left:0;right:0;bottom:0;background:rgba(0,0,0,.85);z-index:1000;justify-content:center;align-items:center;padding:15px}.md.a{display:flex}.mc{background:#1a1a2e;border-radius:12px;width:100%;max-width:500px;max-height:85vh;overflow-y:auto}.mh{padding:15px;border-bottom:1px solid rgba(255,255,255,.1);display:flex;justify-content:space-between;align-items:center}.mh h2{font-size:1.1rem}.mx{background:none;border:none;color:#888;font-size:1.5rem;cursor:pointer}.mb{padding:15px}.kw-detail{text-align:center}.kw-detail .main-score{font-size:2rem;font-weight:700;margin:15px 0}.kw-detail .cat-badge{display:inline-block;padding:4px 12px;background:rgba(255,255,255,.05);border-radius:20px;font-size:.8rem;color:#888;margin-bottom:15px}.kw-detail .metrics-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:20px}.kw-detail .metric{background:rgba(0,0,0,.2);border-radius:8px;padding:12px}.kw-detail .metric .lbl{font-size:.7rem;color:#888}.kw-detail .metric .val{font-size:1.2rem;font-weight:600;margin-top:4px}.kw-detail .related{margin-top:20px;text-align:left}.kw-detail .related h4{font-size:.85rem;color:#888;margin-bottom:10px}.kw-detail .related-item{display:flex;justify-content:space-between;padding:8px;background:rgba(255,255,255,.02);border-radius:6px;margin-bottom:6px;font-size:.8rem}.kw-detail .exc-btn{width:100%;margin-top:20px;padding:12px;background:rgba(255,107,107,.15);border:1px solid rgba(255,107,107,.4);color:#FF6B6B;border-radius:8px;cursor:pointer;font-size:.9rem;transition:all .2s}.kw-detail .exc-btn:hover{background:rgba(255,107,107,.25)}.exc-panel{background:rgba(255,107,107,.05);border:1px solid rgba(255,107,107,.2);border-radius:10px;padding:15px;margin-bottom:15px}.exc-panel h4{font-size:.85rem;color:#FF6B6B;margin-bottom:10px}.exc-panel .exc-list{display:flex;flex-wrap:wrap;gap:6px}.exc-panel .exc-tag{display:inline-flex;align-items:center;gap:5px;padding:4px 10px;background:rgba(255,107,107,.1);border:1px solid rgba(255,107,107,.3);border-radius:15px;font-size:.75rem;color:#FF6B6B}.exc-panel .exc-tag .remove{cursor:pointer;font-weight:bold;opacity:.7}.exc-panel .exc-tag .remove:hover{opacity:1}.add-panel{background:rgba(78,205,196,.05);border:1px solid rgba(78,205,196,.2);border-radius:10px;padding:15px;margin-bottom:15px}.add-panel h4{font-size:.85rem;color:#4ECDC4;margin-bottom:10px}.add-panel .add-form{display:flex;gap:8px}.add-panel input{flex:1;padding:8px 12px;border:1px solid rgba(255,255,255,.1);background:rgba(0,0,0,.2);color:#fff;border-radius:6px;font-size:.85rem}.add-panel input::placeholder{color:#666}.add-panel button{padding:8px 16px;background:rgba(78,205,196,.2);border:1px solid #4ECDC4;color:#4ECDC4;border-radius:6px;cursor:pointer;font-size:.85rem}.add-panel button:hover{background:rgba(78,205,196,.3)}@media(max-width:600px){.gc{grid-template-columns:1fr 1fr}.kw-grid,.all-grid{grid-template-columns:1fr}.stats{gap:15px}.add-panel .add-form{flex-direction:column}}</style></head><body><header class="h"><h1>世代別トレンド分析</h1><p>Generation-based Trend Analysis</p><div class="ver">v7.5 - 自動トレンド検出対応</div><div class="info"><span>📰 News</span><span>🎬 YouTube</span><span>📚 Wikipedia</span><span>🔥 自動トレンド</span><span>🔄 毎日更新</span></div></header><div class="c"><button class="b a" data-c="jp">🇯🇵 日本</button><button class="b" data-c="kr">🇰🇷 韓国</button></div><div class="m"><div class="stats"><div class="stat"><div class="v" id="totalRefsVal">-</div><div class="l">総参照数</div></div><div class="stat"><div class="v">3か月</div><div class="l">分析期間</div></div><div class="stat"><div class="v" id="kwCount">-</div><div class="l">キーワード</div></div><div class="stat"><div class="v" id="excCount">0</div><div class="l">除外中</div></div></div><div id="summary"><div class="ld" id="loader"><div class="sp"></div><div class="ld-pct">0%</div><div class="prog"><div class="prog-bar"></div></div><div class="ld-msg">データを取得しています</div></div></div><div id="detail" class="detail"></div></div><div class="md" id="modal"><div class="mc"><div class="mh"><h2 id="mt">キーワード詳細</h2><button class="mx" onclick="closeM()">&times;</button></div><div class="mb" id="mbd"></div></div></div><script>let co='jp',curGen=null,excList=[],progTimer=null;function updateProg(pct,msg){const l=document.getElementById('loader');if(!l)return;const p=l.querySelector('.ld-pct');const b=l.querySelector('.prog-bar');const m=l.querySelector('.ld-msg');if(p)p.textContent=pct+'%';if(b)b.style.width=pct+'%';if(m&&msg)m.textContent=msg}function startProg(msg){let pct=0;updateProg(0,msg);progTimer=setInterval(()=>{pct+=Math.random()*15;if(pct>90)pct=90;updateProg(Math.round(pct),msg)},200)}function stopProg(){if(progTimer){clearInterval(progTimer);progTimer=null}updateProg(100,'完了')}async function loadExcludeList(){try{const r=await fetch('/api/exclude?country='+co);const d=await r.json();excList=d.excludedKeywords||[];document.getElementById('excCount').textContent=excList.length}catch{excList=[]}}async function saveExcludeList(){try{await fetch('/api/exclude?country='+co,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({keywords:excList})});document.getElementById('excCount').textContent=excList.length}catch(e){console.error('除外リスト保存失敗',e)}}async function addExclude(kw){if(!excList.includes(kw)){excList.push(kw);await saveExcludeList();if(curGen)loadGen(curGen);closeM()}}async function removeExclude(kw){excList=excList.filter(k=>k!==kw);await saveExcludeList();if(curGen)loadGen(curGen)}document.querySelectorAll('[data-c]').forEach(b=>{b.onclick=async()=>{document.querySelectorAll('[data-c]').forEach(x=>x.classList.remove('a'));b.classList.add('a');co=b.dataset.c;curGen=null;document.getElementById('detail').classList.remove('a');await loadExcludeList();loadSummary()}});function fmtNum(n,allowZero){if(n===null||n===undefined)return'-';if(n===0)return allowZero?'0':'-';if(n>=1000000)return(n/1000000).toFixed(1)+'M';if(n>=1000)return(n/1000).toFixed(1)+'K';return n}async function loadSummary(){document.getElementById('summary').innerHTML='<div class="ld" id="loader"><div class="sp"></div><div class="ld-pct">0%</div><div class="prog"><div class="prog-bar"></div></div><div class="ld-msg">データを取得しています</div></div>';document.getElementById('detail').classList.remove('a');startProg('サマリーを読み込み中...');try{const r=await fetch('/api/summary?country='+co);const d=await r.json();stopProg();document.getElementById('totalRefsVal').textContent=fmtNum(d.totalRefs);document.getElementById('kwCount').textContent=d.generations.reduce((s,g)=>s+g.keywordCount,0);renderSummary(d)}catch(e){stopProg();document.getElementById('summary').innerHTML='<div class="ld">エラー</div>'}}function renderSummary(d){let h='<div class="gc">';for(const g of d.generations||[]){const noData=g.noData||g.keywordCount===0;h+='<div class="gcard'+(noData?' no-data':'')+'" style="border-top-color:'+g.color+'" onclick="loadGen(\\''+g.key+'\\')">';h+='<div class="icon">'+g.icon+'</div>';h+='<div class="name">'+g.name+'</div>';h+='<div class="age">'+g.age+'</div>';if(noData){h+='<div class="no-data-msg">データ収集中...</div>'}else{h+='<div class="top-kw">';for(const k of g.topKeywords||[]){h+='<span class="kw">'+esc(k.keyword)+'</span>'}h+='</div>';h+='<div class="refs">📊 '+fmtNum(g.totalRefs)+' refs</div>';h+='<div class="cnt">'+g.keywordCount+'キーワード →</div>'}h+='</div>'}h+='</div>';document.getElementById('summary').innerHTML=h}async function loadGen(genKey){curGen=genKey;document.getElementById('summary').style.display='none';document.getElementById('detail').classList.add('a');document.getElementById('detail').innerHTML='<div class="ld" id="loader"><div class="sp"></div><div class="ld-pct">0%</div><div class="prog"><div class="prog-bar"></div></div><div class="ld-msg">世代データを読み込んでいます</div></div>';startProg('世代データを取得中...');try{const r=await fetch('/api/generation?country='+co+'&gen='+genKey);const d=await r.json();stopProg();document.getElementById('totalRefsVal').textContent=fmtNum(d.totalRefs);document.getElementById('kwCount').textContent=d.totalKeywords;renderGen(d)}catch(e){stopProg();document.getElementById('detail').innerHTML='<div class="ld">エラー</div>'}}function renderGen(d){let h='<div class="dh" style="border-left:4px solid '+d.color+'">';h+='<div class="icon">'+d.icon+'</div>';h+='<div class="info"><div class="name">'+d.name+'</div><div class="sub">'+d.age+' ('+d.birth+') / '+d.period+'</div><div class="refs">📊 総参照数: '+fmtNum(d.totalRefs)+'</div></div>';h+='<button class="back" onclick="backToSummary()">← 戻る</button></div>';h+='<div class="add-panel"><h4>➕ キーワードを追加</h4><div class="add-form"><input type="text" id="newKw" placeholder="追加したいキーワード" onkeypress="if(event.key===\\'Enter\\')addCustomKw()"><select id="newCat" style="padding:8px;border:1px solid rgba(255,255,255,.1);background:rgba(0,0,0,.2);color:#fff;border-radius:6px;font-size:.85rem"><option value="">カテゴリ自動</option></select><button onclick="addCustomKw()">追加</button></div></div>';loadCategories();if(excList.length>0){h+='<div class="exc-panel"><h4>🚫 除外中 ('+excList.length+'件)</h4><div class="exc-list">';for(const e of excList){h+='<span class="exc-tag">'+esc(e)+' <span class="remove" onclick="removeExclude(\\''+esc(e)+'\\')">×</span></span>'}h+='</div></div>'}if(d.notice){h+='<div style="background:rgba(255,193,7,.1);border:1px solid rgba(255,193,7,.3);border-radius:8px;padding:10px;margin-bottom:15px;font-size:.8rem;color:#ffc107">⚠️ '+d.notice+'</div>'}const mainCats=(d.categories||[]).filter(cat=>cat.keywords.length>0);if(mainCats.length>0){h+='<div class="cats">';for(const cat of mainCats){h+='<div class="cat" onclick="toggleCat(event,this)">';h+='<div class="cat-h" style="border-left-color:'+d.color+'">';h+='<span class="arrow">▶</span>';h+='<span class="cat-name">'+esc(cat.name)+'</span>';h+='<span class="cat-score" style="color:'+d.color+'">'+cat.keywords.reduce((s,k)=>s+(k.score||0),0).toFixed(1)+' pts</span>';h+='<span class="cat-refs">'+fmtNum(cat.keywords.reduce((s,k)=>s+(k.totalRefs||0),0))+' refs</span>';h+='<span class="cat-cnt">'+cat.keywords.length+'件</span></div>';h+='<div class="cat-body"><div class="kw-grid">';cat.keywords.forEach((kw,i)=>{h+='<div class="kw-card" onclick="event.stopPropagation();showKw(\\''+d.key+'\\',\\''+esc(kw.keyword)+'\\')">';h+='<div class="rank">#'+(i+1)+'</div>';h+='<div class="kw-info"><div class="kw-name">'+esc(kw.keyword)+'</div>';h+='<div class="kw-metrics"><span>📰'+(kw.news||0)+'</span><span>🎬'+(kw.yt||0)+'</span><span>📚'+(kw.wiki||0)+'</span></div></div>';h+='<div><div class="kw-score" style="color:'+d.color+'">'+(kw.score||0)+'</div><div class="kw-refs">'+fmtNum(kw.totalRefs||0)+'</div></div></div>'});h+='</div></div></div>'}h+='</div>'}const mainKws=d.allKeywords||[];h+='<div class="all-kw"><h3>📋 全キーワード一覧（スコア順）</h3><div class="all-grid">';mainKws.forEach((kw,i)=>{h+='<div class="all-item" onclick="showKw(\\''+d.key+'\\',\\''+esc(kw.keyword)+'\\')">';h+='<span class="name">'+(i+1)+'. '+esc(kw.keyword)+'</span>';h+='<span class="cat">'+esc(kw.category||'')+'</span>';h+='<span class="score" style="color:'+d.color+'">'+(kw.score||0)+'</span></div>'});h+='</div></div>';const customKws=d.customKeywords||[];if(customKws.length>0){h+='<div class="all-kw" style="margin-top:20px;background:rgba(78,205,196,.05);border:1px solid rgba(78,205,196,.2);border-radius:10px;padding:15px"><h3 style="color:#4ECDC4">🔍 手動追加キーワード（'+customKws.length+'件）</h3><div class="all-grid" style="margin-top:10px">';customKws.forEach((kw,i)=>{h+='<div class="all-item" style="background:rgba(78,205,196,.1);border:1px solid rgba(78,205,196,.3)" onclick="showKw(\\''+d.key+'\\',\\''+esc(kw.keyword)+'\\')">';h+='<span class="name">'+esc(kw.keyword)+'</span>';h+='<span class="cat">'+esc(kw.category||'')+'</span>';h+='<span class="score" style="color:#4ECDC4">'+(kw.score||0)+'</span></div>'});h+='</div></div>'}const autoTrends=d.autoTrends||[];if(autoTrends.length>0){h+='<div class="all-kw" style="margin-top:20px;background:rgba(255,193,7,.05);border:1px solid rgba(255,193,7,.2);border-radius:10px;padding:15px"><h3 style="color:#ffc107">🔥 自動検出トレンド（'+autoTrends.length+'件）<span style="font-size:.7rem;color:#888;margin-left:8px">Google Trends急上昇から自動検出</span></h3><div class="all-grid" style="margin-top:10px">';autoTrends.forEach((kw,i)=>{h+='<div class="all-item" style="background:rgba(255,193,7,.1);border:1px solid rgba(255,193,7,.3)" onclick="showKw(\\''+d.key+'\\',\\''+esc(kw.keyword)+'\\')">';h+='<span class="name">🔥 '+esc(kw.keyword)+'</span>';h+='<span class="cat">'+esc(kw.category||'')+'</span>';h+='<span class="score" style="color:#ffc107">'+(kw.score||0)+'</span></div>'});h+='</div></div>'}document.getElementById('detail').innerHTML=h}function toggleCat(e,el){if(e.target.closest('.kw-card'))return;el.classList.toggle('open')}function backToSummary(){document.getElementById('summary').style.display='block';document.getElementById('detail').classList.remove('a');curGen=null;loadSummary()}async function showKw(gen,kw){document.getElementById('modal').classList.add('a');document.getElementById('mt').textContent=kw;document.getElementById('mbd').innerHTML='<div class="ld"><div class="sp"></div></div>';try{const r=await fetch('/api/keyword?country='+co+'&gen='+gen+'&kw='+encodeURIComponent(kw));const d=await r.json();renderKwDetail(d,kw)}catch{document.getElementById('mbd').innerHTML='<div class="ld">エラー</div>'}}function renderKwDetail(d,kw){let h='<div class="kw-detail">';h+='<div style="font-size:.8rem;color:#888;margin-bottom:5px">'+(d.genIcon||'')+'  '+(d.genName||'')+'</div>';h+='<div class="main-score" style="color:'+(d.color||'#888')+'">'+(d.score||0)+' pts</div>';h+='<div class="cat-badge">'+esc(d.category||'その他')+'</div>';h+='<div class="metrics-grid">';h+='<div class="metric"><div class="lbl">📰 ニュース</div><div class="val" style="color:#FF6B6B">'+(d.news||0)+'</div></div>';h+='<div class="metric"><div class="lbl">🎬 YouTube</div><div class="val" style="color:#4ECDC4">'+(d.yt||0)+'</div></div>';h+='<div class="metric"><div class="lbl">📚 Wikipedia</div><div class="val" style="color:#DDA0DD">'+fmtNum(d.wiki||0)+'</div></div>';h+='</div>';h+='<div style="text-align:center;font-size:.75rem;color:#888;margin-bottom:10px">📊 総参照数: '+fmtNum(d.totalRefs||0)+'</div>';if(d.ytQuality!==undefined&&d.ytQuality>0){h+='<div style="text-align:center;font-size:.75rem;color:#888;margin-bottom:10px">YouTube品質: +'+d.ytQuality+'</div>'}if(d.relatedKeywords&&d.relatedKeywords.length>0){h+='<div class="related"><h4>同カテゴリのキーワード</h4>';for(const r of d.relatedKeywords){h+='<div class="related-item"><span>'+esc(r.keyword)+'</span><span style="color:'+(d.color||'#888')+'">'+(r.score||0)+' pts</span></div>'}h+='</div>'}h+='<button class="exc-btn" onclick="addExclude(\\''+esc(kw)+'\\')">🚫 このキーワードを除外</button>';h+='</div>';document.getElementById('mbd').innerHTML=h}function closeM(){document.getElementById('modal').classList.remove('a')}document.getElementById('modal').onclick=e=>{if(e.target===document.getElementById('modal'))closeM()};async function loadCategories(){try{const r=await fetch('/api/categories?country='+co);const d=await r.json();const sel=document.getElementById('newCat');if(sel&&d.categories){sel.innerHTML='<option value="">カテゴリ自動</option>';d.categories.forEach(c=>{sel.innerHTML+='<option value="'+c+'">'+c+'</option>'})}}catch{}}async function addCustomKw(){const inp=document.getElementById('newKw');const cat=document.getElementById('newCat');const kw=inp.value.trim();const catVal=cat?cat.value:'';if(!kw||!curGen)return;inp.disabled=true;if(cat)cat.disabled=true;const btn=document.querySelector('.add-form button');btn.textContent='分析中...';btn.disabled=true;try{const r=await fetch('/api/analyze-custom?country='+co+'&gen='+curGen+'&kw='+encodeURIComponent(kw)+'&cat='+encodeURIComponent(catVal));const d=await r.json();if(d.success){inp.value='';if(cat)cat.value='';loadGen(curGen)}else{alert('追加失敗: '+(d.error||'不明なエラー'))}}catch(e){alert('エラー: '+e.message)}finally{inp.disabled=false;if(cat)cat.disabled=false;btn.textContent='追加';btn.disabled=false}}function esc(s){if(!s)return'';const d=document.createElement('div');d.textContent=s;return d.innerHTML}loadExcludeList().then(()=>loadSummary())</script></body></html>`;
}
