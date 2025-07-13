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
    print(f"--- OCR Result ---\n{text}\n--------------------", flush=True)
    return text

def robust_parse_pfc(ocr_text):
    """
    OCRテキストからPFCの値を頑健に抽出する。
    正規表現を使い、キーワードの後に現れる最初の数値を抽出する。
    """
    pfc = {'P': 0.0, 'F': 0.0, 'C': 0.0}
    
    # 検索しやすいように、テキストから改行をスペースに置換
    # これにより、キーワードと数値が別々の行にあっても検索できる
    flat_text = ocr_text.replace('\n', ' ')

    # キーワードと、その後に現れる最初の数値を抽出するための正規表現パターン
    # 例: 「たんぱく質 ... 123.4 / ...」というテキストから「123.4」を捕捉
    patterns = {
        'P': r'(たんぱく質|タンパク質|protein)\s*.*?([\d.]+)',
        'F': r'(脂質|ししつ|fat)\s*.*?([\d.]+)',
        'C': r'(炭水化物|たんすいかぶつ|carbohydrate)\s*.*?([\d.]+)'
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
                # 変換に失敗した場合はスキップ
                print(f"Could not parse value for {key} from match: {match.groups()}", flush=True)
                continue
    
    print(f"--- Parsed PFC (Keywords) ---\nP: {pfc['P']}, F: {pfc['F']}, C: {pfc['C']}\n------------------", flush=True)
    
    # 3つの栄養素がすべて0の場合は、解析失敗とみなす
    if pfc['P'] == 0.0 and pfc['F'] == 0.0 and pfc['C'] == 0.0:
        raise ValueError(f"PFCの値をテキストから抽出できませんでした。 OCR結果: '{ocr_text}'")
        
    return pfc


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