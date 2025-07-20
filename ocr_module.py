import easyocr
import re

# ★★★【修正点】★★★
# アプリ起動時に一度だけモデルを読み込むように、関数の外で初期化する
print("Initializing EasyOCR Reader... This may take a moment on first boot.", flush=True)
reader = easyocr.Reader(['ja', 'en'])
print("EasyOCR Reader initialized successfully.", flush=True)


def calculate_pfc_from_image_final(image_data):
    """
    【最終完全版】EasyOCRの初期化を起動時に行うバージョン
    """
    try:
        # ★★★【修正点】★★★
        # 初期化済みのreaderをグローバル変数として使用する
        global reader
        
        # paragraph=True は、文章として意味のあるまとまりでテキストを連結するオプション
        result = reader.readtext(image_data, detail=0, paragraph=True) 
        full_text = ' '.join(result)
        
    except Exception as e:
        print(f"!!! OCR processing failed: {e}", flush=True)
        return None

    # --- 正規表現による解析 ---
    # （この部分のロジックは変更ありません）
    p_gram, f_gram, c_gram = None, None, None

    keyword_p = r'たんぱく(?:質|貨)'
    keyword_f = r'脂(?:質|貨)'
    keyword_c = r'炭水化物'

    pf_match_slash = re.search(f'{keyword_p}\\s*{keyword_f}\\s*(\\d+\\.\\d+)\\s*/\\s*\\d+\\.\\d+[^.\\d]*(\\d+\\.\\d+)', full_text)
    pf_match_no_slash = re.search(f'{keyword_p}\\s*{keyword_f}\\s*(\\d+\\.\\d+)\\s+\\d+\\.\\d+[^.\\d]*(\\d+\\.\\d+)', full_text)
    pf_match_no_space = re.search(f'{keyword_p}{keyword_f}(\\d+\\.\\d+)(\\d+\\.\\d+)(\\d+\\.\\d+)', full_text)

    if pf_match_slash:
        p_gram = float(pf_match_slash.group(1))
        f_gram = float(pf_match_slash.group(2))
    elif pf_match_no_slash:
        p_gram = float(pf_match_no_slash.group(1))
        f_gram = float(pf_match_no_slash.group(2))
    elif pf_match_no_space:
        p_gram = float(pf_match_no_space.group(1))
        f_gram = float(pf_match_no_space.group(3))
    else:
        p_match = re.search(f'{keyword_p}\\s*(\\d+\\.\\d+)', full_text)
        if p_match: p_gram = float(p_match.group(1))
        
        f_match = re.search(f'{keyword_f}\\s*(\\d+\\.\\d+)', full_text)
        if f_match: f_gram = float(f_match.group(1))

    c_match = re.search(f'{keyword_c}\\s*(?:糖質\\s*)?(\\d+\\.\\d+)', full_text)
    if c_match: c_gram = float(c_match.group(1))

    if p_gram is None or f_gram is None or c_gram is None:
        print("!!! Could not extract all PFC values from OCR result.", flush=True)
        print(f"  OCR Text: {''.join(full_text.split())}", flush=True)
        print(f"  Found values: P={p_gram}, F={f_gram}, C={c_gram}", flush=True)
        return None

    # --- 計算処理 ---
    p_cal, f_cal, c_cal = p_gram * 4, f_gram * 9, c_gram * 4
    total_cal = p_cal + f_cal + c_cal
    if total_cal == 0:
        return {'P': 0, 'F': 0, 'C': 0}

    p_ratio = (p_cal / total_cal) * 100
    f_ratio = (f_cal / total_cal) * 100
    c_ratio = (c_cal / total_cal) * 100

    return {'P': p_ratio, 'F': f_ratio, 'C': c_ratio}