# Trends Data Collector - GitHub Actions 設定ガイド

GitHub Actionsで毎日トレンドデータを収集し、Cloudflare KVに蓄積するスクリプト。

---

## 📋 必要な情報

以下の3つの値をメモしておいてください：

| 項目 | 値 | 取得場所 |
|------|-----|----------|
| `CF_API_TOKEN` | `HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U` | Cloudflare Dashboard > My Profile > API Tokens |
| `CF_ACCOUNT_ID` | `dddb47cb848a3a6100f19fdcd6811212` | Cloudflare Dashboard > Workers > 右側に表示 |
| `CF_KV_NAMESPACE_ID` | `f5c396bf00af493abad3568261143511` | Workers > KV > TRENDS_KV の ID |

---

## 🚀 セットアップ手順（ステップバイステップ）

### ステップ1: GitHubリポジトリを作成

1. **GitHubにアクセス**: https://github.com/new

2. **リポジトリを作成**:
   - Repository name: `trends-cron`
   - Public または Private を選択
   - "Create repository" をクリック

### ステップ2: ローカルでファイルを準備

コマンドプロンプトまたはPowerShellで以下を実行:

```bash
# trends-cronフォルダに移動
cd "C:\Users\work\Desktop\Claudeフォルダ\AI\trends-cron"

# Gitリポジトリを初期化
git init

# 必要なフォルダ構造を作成
mkdir -p .github/workflows

# 全ファイルをステージング
git add .

# 初回コミット
git commit -m "Initial commit: trends data collector"

# GitHubリポジトリを紐付け（YOUR_USERNAMEを自分のGitHubユーザー名に変更）
git remote add origin https://github.com/YOUR_USERNAME/trends-cron.git

# mainブランチにプッシュ
git branch -M main
git push -u origin main
```

### ステップ3: GitHub Secretsを設定

これが最も重要なステップです。

1. **GitHubリポジトリにアクセス**:
   ```
   https://github.com/YOUR_USERNAME/trends-cron
   ```

2. **Settings タブをクリック**

3. **左メニューから "Secrets and variables" → "Actions" を選択**

4. **"New repository secret" ボタンをクリック**

5. **以下の3つのSecretを追加**:

   #### Secret 1: CF_API_TOKEN
   ```
   Name: CF_API_TOKEN
   Secret: HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U
   ```
   → "Add secret" をクリック

   #### Secret 2: CF_ACCOUNT_ID
   ```
   Name: CF_ACCOUNT_ID
   Secret: dddb47cb848a3a6100f19fdcd6811212
   ```
   → "Add secret" をクリック

   #### Secret 3: CF_KV_NAMESPACE_ID
   ```
   Name: CF_KV_NAMESPACE_ID
   Secret: f5c396bf00af493abad3568261143511
   ```
   → "Add secret" をクリック

### ステップ4: GitHub Actionsを有効化

1. **"Actions" タブをクリック**

2. **緑のボタン "I understand my workflows, go ahead and enable them" をクリック**

### ステップ5: 手動で初回実行（テスト）

1. **Actions タブで "Collect Trends Data" をクリック**

2. **右側の "Run workflow" ボタンをクリック**

3. **"Run workflow" を再度クリック**

4. **実行結果を確認**（緑のチェックマークが表示されれば成功）

---

## 📅 スケジュール

| 実行タイミング | 説明 |
|----------------|------|
| **毎日 UTC 0:00** | JST 9:00 に自動実行 |
| **手動実行** | Actions タブから "Run workflow" で即時実行 |

---

## 📁 ファイル構造

```
trends-cron/
├── .github/
│   └── workflows/
│       └── collect-trends.yml  # GitHub Actions 設定
├── collect_trends.py           # データ収集スクリプト
└── README.md                   # このファイル
```

---

## 🔍 KVに保存されるデータ

### 日次データ
キー: `daily_{country}_{category}_{date}`

```json
{
  "date": "2026-02-08",
  "country": "jp",
  "category": "tech",
  "keywords": {
    "生成AI": 100,
    "ChatGPT": 82,
    "Claude": 45
  }
}
```

### 履歴インデックス
キー: `history_{country}_{category}`

```json
{
  "dates": ["2026-02-06", "2026-02-07", "2026-02-08"]
}
```

---

## 🛠️ トラブルシューティング

### ❌ Workflowが失敗する場合

1. **Secretsが正しく設定されているか確認**
   - Settings > Secrets and variables > Actions
   - 3つのSecretがすべて存在するか確認

2. **APIトークンの権限を確認**
   - Cloudflare Dashboard > My Profile > API Tokens
   - トークンに "Workers KV Storage" の編集権限があるか確認

3. **ログを確認**
   - Actions > 失敗したワークフロー > 詳細を展開
   - エラーメッセージを確認

### ❌ データが保存されない場合

1. **KVネームスペースIDを確認**
   - Cloudflare Dashboard > Workers > KV
   - `TRENDS_KV` のIDが正しいか確認

2. **手動でスクリプトをテスト**
   ```bash
   cd trends-cron

   # 環境変数を設定
   set CF_API_TOKEN=HPQFIKr1hszgJckPLBzdBaR5g00ePOGV2b6ojO5U
   set CF_ACCOUNT_ID=dddb47cb848a3a6100f19fdcd6811212
   set CF_KV_NAMESPACE_ID=f5c396bf00af493abad3568261143511

   # 実行
   python collect_trends.py
   ```

---

## ✅ 設定完了後の確認

1. **トレンド分析ダッシュボードにアクセス**:
   ```
   https://long-trends.kyunghok17.workers.dev
   ```

2. **変化率（%）が表示されるようになる**
   - 数日分のデータが蓄積されると、各キーワードの横に変化率が表示されます
   - 📈 上昇 / ➡️ 安定 / 📉 下降

---

## 📞 サポート

問題が発生した場合は、以下を確認してください:
- Cloudflare KV Namespace が存在するか
- API Token が有効か
- GitHub Secrets が正しく設定されているか
