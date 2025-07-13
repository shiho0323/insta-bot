import re
import numpy as np
import cv2
import pytesseract

def ocr_from_bytes(img_bytes):
    """
    画像バイトデータからOCRでテキストを抽出する。
    OCR精度向上のため、画像の前処理を強化する。
    """
    # バイトデータをnumpy配列に変換
    nparr = np.frombuffer(img_bytes, np.uint8)
    # numpy配列を画像としてデコード
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 1. 画像を拡大して解像度を上げる (OCR精度向上に寄与)
    height, width, _ = img.shape
    img_resized = cv2.resize(img, (width * 2, height * 2), interpolation=cv2.INTER_CUBIC)

    # 2. グレースケール化
    gray = cv2.cvtColor(img_resized, cv2.COLOR_BGR2GRAY)

    # 3. ノイズ除去 (メディアンフィルタはゴマ塩ノイズに強い)
    blurred = cv2.medianBlur(gray, 3)

    # 4. 二値化 (OTSUのアルゴリズムで自動的にしきい値を決定)
    _, th = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # 5. OCR実行時の設定 (PSM 6は、テキストが単一のブロックであると仮定)
    custom_config = r'--oem 3 --psm 6'
    text = pytesseract.image_to_string(th, lang='jpn+eng', config=custom_config)
    print(f"--- OCR Result ---\n{text}\n--------------------")
    return text

def robust_parse_pfc(ocr_text):
    """
    OCRテキストからPFCの値を頑健に抽出する。
    キーワード検索と、失敗した場合の数値のみの抽出を試みる。
    """
    pfc = {'P': 0.0, 'F': 0.0, 'C': 0.0}
    
    # --- プランA: キーワードに基づいた検索 ---
    # 検索しやすいようにテキストを整形
    full_text_for_keywords = ' '.join(ocr_text.strip().split('\n'))

    patterns = {
        'P': r'(たんぱく質|タンパク質|protein|p)\s*[:：]?\s*([\d.]+)',
        'F': r'(脂質|ししつ|fat|f)\s*[:：]?\s*([\d.]+)',
        'C': r'(炭水化物|たんすいかぶつ|carbo|c)\s*[:：]?\s*([\d.]+)'
    }

    found_count = 0
    for key, pattern in patterns.items():
        match = re.search(pattern, full_text_for_keywords, re.IGNORECASE)
        if match:
            try:
                value = float(match.group(2))
                pfc[key] = value
                found_count += 1
            except (ValueError, IndexError):
                continue
    
    # キーワード検索で2つ以上見つかれば、成功とみなす
    if found_count >= 2:
        print(f"--- Parsed PFC (Keywords) ---\nP: {pfc['P']}, F: {pfc['F']}, C: {pfc['C']}\n------------------")
        return pfc

    # --- プランB: プランAが失敗した場合のフォールバック ---
    print("--- Keywords not found. Falling back to number extraction. ---")
    
    # OCRでよくある誤認識を置換
    text_cleaned = ocr_text.replace('g', '9').replace('o', '0').replace('O', '0').replace('l', '1').replace('i', '1')
    
    # テキストから全ての数値（整数・小数）を抽出
    numbers = re.findall(r'[\d.]+', text_cleaned)
    float_numbers = []
    for num_str in numbers:
        try:
            # 連続したドットなど、不正な数値をフィルタリング
            if num_str.count('.') <= 1:
                float_numbers.append(float(num_str))
        except ValueError:
            continue

    # 3つ以上の数値が見つかった場合、順番にP, F, Cと仮定する
    if len(float_numbers) >= 3:
        pfc['P'] = float_numbers[0]
        pfc['F'] = float_numbers[1]
        pfc['C'] = float_numbers[2]
        print(f"--- Parsed PFC (Fallback) ---\nP: {pfc['P']}, F: {pfc['F']}, C: {pfc['C']}\n------------------")
        return pfc

    # 全てのプランが失敗した場合
    raise ValueError(f"PFCの値をテキストから抽出できませんでした。 OCR結果: '{ocr_text}'")


def calculate_ratio_from_parsed(parsed_pfc):
    """
    解析済みのPFC辞書からカロリーベースのPFC比率を計算する。
    """
    P_CAL_PER_G = 4
    F_CAL_PER_G = 9
    C_CAL_PER_G = 4

    p_cal = parsed_pfc.get('P', 0.0) * P_CAL_PER_G
    f_cal = parsed_pfc.get('F', 0.0) * F_CAL_PER_G
    c_cal = parsed_pfc.get('C', 0.0) * C_CAL_PER_G

    total_cal = p_cal + f_cal + c_cal

    if total_cal == 0:
        return {'P': 0.0, 'F': 0.0, 'C': 0.0}

    return {
        'P': (p_cal / total_cal) * 100,
        'F': (f_cal / total_cal) * 100,
        'C': (c_cal / total_cal) * 100,
    }