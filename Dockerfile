# 1. ベースとなるPythonの環境を選択
FROM python:3.11-slim

# 2. apt-get（OSのパッケージ管理ツール）を更新し、Tesseract OCRをインストール
#    pytesseractライブラリがこれを使います
RUN apt-get update && apt-get install -y tesseract-ocr tesseract-ocr-jpn

# 3. 作業ディレクトリを設定
WORKDIR /app

# 4. 必要なPythonライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. プロジェクトのファイルを作業ディレクトリにコピー
#    (app.py, ocr_module.py, download_models.py など)
COPY . .

# ★★★【今回の修正点】★★★
# 6. ビルドの段階で、AIモデルのダウンロード用スクリプトを実行する
RUN python download_models.py

# 7. アプリが使用するポートを公開
EXPOSE 10000

# 8. コンテナ起動時に実行するコマンド（アプリの起動）
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000"]