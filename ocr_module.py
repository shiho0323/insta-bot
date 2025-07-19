import re
from io import BytesIO
from PIL import Image
import numpy as np
import cv2
import pytesseract

# グラム当たりのカロリー定数
P_CAL_PER_G = 4.0
F_CAL_PER_G = 9.0
C_CAL_PER_G = 4.0

def _preprocess(img: np.ndarray) -> np.ndarray:
    """グレースケール→ブラー→大津二値化→モルフォロジーで文字を強調"""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
    closed = cv2.morphologyEx(th, cv2.MORPH_CLOSE, kernel, iterations=1)
    return closed

def _perform_ocr(img: np.ndarray) -> str:
    """文字認識。日本語と英語に対応し、様々な形式の栄養成分表示に対応"""
    # ★言語に 'jpn' を追加し、認識できる文字種を増やす
    config = '--psm 6' # tessedit_char_whitelist は削除し、日本語を認識できるようにする
    text = pytesseract.image_to_string(img, lang='jpn+eng', config=config)
    
    # 【デバッグ用】どんなテキストが認識されたかログに出力したい場合は、以下の行のコメントを解除してください
    # print(f"--- OCR Result ---\n{text}\n--------------------", flush=True)
    
    return text

def _robust_parse_pfc(text: str) -> dict:
    """
    【強化版】P, F, C の数値を様々なキーワードから頑健に抽出する。
    「たんぱく質」「脂質」「炭水化物」などの日本語キーワードに対応。
    """
    pfc = {'P': 0.0, 'F': 0.0, 'C': 0.0}
    
    # 検索しやすいように、テキストから改行や空白を整理
    flat_text = ' '.join(text.split())

    # キーワードと、その後に現れる最初の数値を抽出するための正規表現パターン
    # 'g'や'グラム'などの単位の有無、コロンやスペースのバリエーションに対応
    patterns = {
        'P': r'(たんぱく質|タンパク質|protein)\s*:?\s*([\d.]+)',
        'F': r'(脂質|ししつ|fat)\s*:?\s*([\d.]+)',
        'C': r'(炭水化物|たんすいかぶつ|carbohydrate)\s*:?\s*([\d.]+)'
    }

    for key, pattern in patterns.items():
        # パターンにマッチするものを探す (大文字・小文字を無視)
        match = re.search(pattern, flat_text, re.IGNORECASE)
        if match:
            try:
                # 見つかった数値部分(group(2))を浮動小数点数に変換
                value_str = match.group(2)
                pfc[key] = float(value_str)
            except (ValueError, IndexError):
                continue # 変換に失敗した場合はスキップ
                
    # 【デバッグ用】パース結果を確認したい場合は以下の行のコメントを解除
    # print(f"--- Parsed PFC ---\nP: {pfc['P']}, F: {pfc['F']}, C: {pfc['C']}\n------------------", flush=True)
        
    return pfc

def ocr_from_bytes(img_bytes: bytes) -> dict:
    """
    画像バイト列→OCR→P,F,C比率を返却
    """
    try:
        pil = Image.open(BytesIO(img_bytes)).convert('RGB')
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("画像デコードに失敗しました")

    # 縦解像度が小さければ拡大
    h = img.shape[0]
    if h < 800:
        scale = 800.0 / h
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # 前処理→OCR→パース
    proc = _preprocess(img)
    raw = _perform_ocr(proc)
    parsed = _robust_parse_pfc(raw) # ★新しい堅牢なパース関数を呼び出す

    # カロリー換算＆比率計算
    p_cal = parsed.get('P', 0.0) * P_CAL_PER_G
    f_cal = parsed.get('F', 0.0) * F_CAL_PER_G
    c_cal = parsed.get('C', 0.0) * C_CAL_PER_G
    total = p_cal + f_cal + c_cal

    if total <= 0:
        return {'P': 0.0, 'F': 0.0, 'C': 0.0}

    return {
        'P': round((p_cal / total) * 100, 2),
        'F': round((f_cal / total) * 100, 2),
        'C': round((c_cal / total) * 100, 2),
    }