# 🚨 緊急セキュリティアラート

## **即座に実行してください**

### 1. **APIキーの無効化**
`launch.bat`ファイルに以下のAPIキーがハードコードされていました：
- API Key: `AKjSshszzjLdguhJAA8KfQw8Vx6b3dWQ`
- API Secret: `nJpifUVTOW1e5bVlET6+BH4KSVvBA4yvIMazD1ozmFVuDyOvH37mtE4219cB1yAW`

**今すぐGMOコインの管理画面でこのAPIキーを削除・無効化してください！**

### 2. **新しいAPIキーの作成**
1. GMOコインにログイン
2. API管理ページで古いキーを削除
3. 新しいAPIキーペアを作成
4. 適切な権限設定（必要最小限の権限のみ）

### 3. **安全な設定方法**
1. `.env.example`をコピーして`.env`ファイルを作成
2. 新しいAPIキーを`.env`ファイルに設定
3. `.env`ファイルは絶対にGitにコミットしない

## 修正済み項目
- ✅ `launch.bat`からAPIキーを削除
- ✅ `.env`ファイルベースの設定に変更
- ✅ `.gitignore`を追加して`.env`ファイルを除外
- ✅ `backend/__init__.py`の修正（ディレクトリ→ファイル）

## 次に必要な作業
1. 新しいAPIキーで`.env`ファイルを設定
2. システムの動作確認
3. このセキュリティアラートファイルを削除 