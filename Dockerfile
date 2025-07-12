# 1. ベースとなる環境を選択
FROM python:3.11-slim

# 2. Tesseract OCRエンジンと日本語パックをインストール
# これにより、OSレベルでOCR機能が使えるようになります。
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-jpn \
    && rm -rf /var/lib/apt/lists/*

# 3. プログラムを置くためのフォルダを作成
WORKDIR /app

# 4. 必要なPythonライブラリをインストール
# まずrequirements.txtだけをコピーしてインストールすることで、
# プログラムのコードだけを変更した際に、毎回ライブラリをインストールし直す必要がなくなり、ビルドが高速化します。
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 5. プログラムの全ファイルをコピー
COPY . .

# 6. このコンテナが起動したときに実行するコマンド
# gunicornを使って、app.pyの中のappという名前のFlaskアプリを起動します。
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "app:app"]