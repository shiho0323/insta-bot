# 1. ベースとなる環境を選択
FROM python:3.11-slim

# 2. 必要なシステムライブラリをインストール
# Tesseractと、OpenCVが必要とするグラフィックライブラリ(libgl1)をインストールします。
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    libgl1 \
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
# タイムアウトを120秒に延長して、重いOCR処理に対応します。
CMD ["gunicorn", "--bind", "0.0.0.0:10000", "--timeout", "120", "app:app"]