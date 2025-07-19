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
    """文字認識。数字と小数点のみを許可して精度向上を図る"""
    config = '--psm 6 -c tessedit_char_whitelist=0123456789.'
    return pytesseract.image_to_string(img, lang='eng', config=config)

def _parse_pfc(text: str) -> dict:
    """P, F, C の数値を正規表現で抽出"""
    parsed = {}
    m = re.search(r'[Pp]:?\s*([0-9]+(?:\.[0-9]+)?)', text)
    if m: parsed['P'] = float(m.group(1))
    m = re.search(r'[Ff]:?\s*([0-9]+(?:\.[0-9]+)?)', text)
    if m: parsed['F'] = float(m.group(1))
    m = re.search(r'[Cc]:?\s*([0-9]+(?:\.[0-9]+)?)', text)
    if m: parsed['C'] = float(m.group(1))
    return parsed

def ocr_from_bytes(img_bytes: bytes) -> dict:
    """
    画像バイト列→OCR→P,F,C比率を返却
    戻り値例：{'P': 25.0, 'F': 50.0, 'C': 25.0}
    """
    # ① PIL読み込みを試す
    try:
        pil = Image.open(BytesIO(img_bytes)).convert('RGB')
        img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    except Exception:
        # ② フォールバックでOpenCVデコード
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("画像デコードに失敗しました")

    # ③ 縦解像度が小さければ拡大
    h = img.shape[0]
    if h < 800:
        scale = 800.0 / h
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)

    # ④ 前処理→OCR→パース
    proc = _preprocess(img)
    raw = _perform_ocr(proc)
    parsed = _parse_pfc(raw)

    # ⑤ カロリー換算＆比率計算
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
