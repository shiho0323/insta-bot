import easyocr
import re

def calculate_pfc_from_image_final(image_data):
    """
    【最終完全版】全てのOCRエラーパターンに対応し、画像データ（バイト列）を直接受け取る
    """
    try:
        # 画像データを直接OCRにかける
        reader = easyocr.Reader(['ja', 'en'])
        # paragraph=True は、文章として意味のあるまとまりでテキストを連結するオプション
        # これにより、キーワードと数値が分離しにくくなる効果が期待できる
        result = reader.readtext(image_data, detail=0, paragraph=True) 
        full_text = ' '.join(result)
        
    except Exception as e:
        print(f"!!! OCR processing failed: {e}", flush=True)
        return None

    p_gram, f_gram, c_gram = None, None, None
    keyword_p = r'たんぱく(?:質|貨)'
    keyword_f = r'脂(?:質|貨)'
    keyword_c = r'炭水化物'

    # パターン1: 理想的なケース（スラッシュ区切り）
    pf_match_slash = re.search(f'{keyword_p}\\s*{keyword_f}\\s*(\\d+\\.\\d+)\\s*/\\s*\\d+\\.\\d+[^.\\d]*(\\d+\\.\\d+)', full_text)
    
    # パターン2: Pのスラッシュが消えたケース（スペース区切り）
    pf_match_no_slash = re.search(f'{keyword_p}\\s*{keyword_f}\\s*(\\d+\\.\\d+)\\s+\\d+\\.\\d+[^.\\d]*(\\d+\\.\\d+)', full_text)

    # パターン3: 全ての区切り文字が消えたケース
    pf_match_no_space = re.search(f'{keyword_p}\\s*{keyword_f}(\\d+\\.\\d+)(\\d+\\.\\d+)(\\d+\\.\\d+)', full_text)

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
        # パターン4: その他の予備処理
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

    # PFCバランスを計算
    p_cal, f_cal, c_cal = p_gram * 4, f_gram * 9, c_gram * 4
    total_cal = p_cal + f_cal + c_cal
    if total_cal == 0:
        return {'P': 0, 'F': 0, 'C': 0}

    p_ratio = (p_cal / total_cal) * 100
    f_ratio = (f_cal / total_cal) * 100
    c_ratio = (c_cal / total_cal) * 100

    # app.pyが期待する形式で辞書を返す
    return {'P': p_ratio, 'F': f_ratio, 'C': c_ratio}