# 1. ベースとなるPythonの環境を選択
FROM python:3.11-slim

# ★★★【修正点】★★★
# 2. OSのパッケージを更新し、Tesseract と OpenCV の依存ライブラリをインストール
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && apt-get clean

# 3. 作業ディレクトリを設定
WORKDIR /app

# 4. 必要なPythonライブラリをインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. プロジェクトのファイルを作業ディレクトリにコピー
COPY . .

# 6. ビルドの段階で、AIモデルのダウンロード用スクリプトを実行する
RUN python download_models.py

# 7. アプリが使用するポートを公開
EXPOSE 10000

# 8. コンテナ起動時に実行するコマンド（アプリの起動）
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:10000", "--timeout", "120"]