import easyocr
# このファイルを実行すると、easyocrが必要なモデルをダウンロード・キャッシュします
easyocr.Reader(['ja', 'en'])