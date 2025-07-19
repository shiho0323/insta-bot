from io import BytesIO
from PIL import Image
import numpy as np
import cv2
import pytesseract

def ocr_from_bytes(img_bytes):
    # PIL→OpenCV 変換はそのまま
    pil = Image.open(BytesIO(img_bytes)).convert('RGB')
    img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)

    # 前処理
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur = cv2.GaussianBlur(gray, (5,5), 0)
    _, th = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # ★ここにカスタム設定を定義して…
    custom_config = (
        '--oem 3 '              # OCR Engine Mode  
        '--psm 6 '              # Page Segmentation Mode  
        '-c tessedit_char_whitelist=0123456789./gcalPFC%'  
    )

    # ★そして image_to_string に渡す
    text = pytesseract.image_to_string(
        th,
        lang='jpn+eng',
        config=custom_config
    )
    return text

def calculate_ratio_from_parsed(parsed):
    kc_p = parsed['P']['current'] * 4
    kc_f = parsed['F']['current'] * 9
    kc_c = parsed['C']['current'] * 4
    total = kc_p + kc_f + kc_c
    return {
        'P': kc_p / total * 100,
        'F': kc_f / total * 100,
        'C': kc_c / total * 100,
    }

import re

def robust_parse_pfc(text):
    # 1) 数字／数字 のペアを含む行だけ抽出 （g の有無は問わない）
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if re.search(r'\d+\.\d+\s*[／/]\s*\d+\.\d+', ln)
    ]
    if len(lines) < 2:
        raise ValueError(f"P/F/Cの行が足りません: {lines}")

    # 2) １行目 → P と F
    def find_pairs(ln):
        # スラッシュ区切りの float ペアをすべて拾う
        return re.findall(r'(\d+\.\d+)\s*[／/]\s*(\d+\.\d+)', ln)

    p_f_pairs = find_pairs(lines[0])
    if len(p_f_pairs) < 2:
        raise ValueError(f"P/F ペアが見つかりません: {lines[0]}")
    p_cur, p_tgt = map(float, p_f_pairs[0])
    f_cur, f_tgt = map(float, p_f_pairs[1])

    # 3) ２行目 → C と Sugar（２ペアあるはずだが、Cだけ見ればOK）
    c_pairs = find_pairs(lines[1])
    if len(c_pairs) < 1:
        raise ValueError(f"Cペアが見つかりません: {lines[1]}")
    c_cur, c_tgt = map(float, c_pairs[0])

    return {
        'P': {'current': p_cur, 'target': p_tgt},
        'F': {'current': f_cur, 'target': f_tgt},
        'C': {'current': c_cur, 'target': c_tgt},
    }

