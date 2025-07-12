import re
import numpy as np
import cv2
import pytesseract

def ocr_from_bytes(img_bytes):
    """
    画像バイトデータからOCRでテキストを抽出する。
    画像の前処理もここで行う。
    """
    # バイトデータをnumpy配列に変換
    nparr = np.frombuffer(img_bytes, np.uint8)
    # numpy配列を画像としてデコード
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    # 画像の前処理（グレースケール化、二値化）はOCRの精度向上に有効
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 適応的しきい値処理など、他の前処理を試すのも良い
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # OCR実行
    # 日本語と英語の言語パックを使用
    text = pytesseract.image_to_string(th, lang='jpn+eng')
    print(f"--- OCR Result ---\n{text}\n--------------------")
    return text

def robust_parse_pfc(ocr_text):
    """
    OCRテキストからPFCの値を頑健に抽出する。
    正規表現を使い、一般的なOCRエラーに対応する。
    """
    pfc = {'P': 0.0, 'F': 0.0, 'C': 0.0}
    
    # 検索しやすいように、テキストから空白や改行を一部整理
    lines = ocr_text.strip().split('\n')
    full_text = ' '.join(lines)

    # キーワードと、それに続く数値を抽出するための正規表現パターン
    # 「たんぱく質」の後にコロンやスペースを挟んで「20.5」のような数字があるパターンを捕捉
    patterns = {
        'P': r'(たんぱく質|タンパク質|protein|p)\s*[:：]?\s*([\d.]+)',
        'F': r'(脂質|ししつ|fat|f)\s*[:：]?\s*([\d.]+)',
        'C': r'(炭水化物|たんすいかぶつ|carbo|c)\s*[:：]?\s*([\d.]+)'
    }

    for key, pattern in patterns.items():
        # パターンにマッチするものを探す (大文字・小文字を無視)
        match = re.search(pattern, full_text, re.IGNORECASE)
        if match:
            try:
                # 見つかった数値部分を浮動小数点数に変換
                value = float(match.group(2))
                pfc[key] = value
            except (ValueError, IndexError):
                # 変換に失敗した場合はスキップ
                print(f"Could not parse value for {key} from match: {match.groups()}")
                continue
    
    print(f"--- Parsed PFC ---\nP: {pfc['P']}, F: {pfc['F']}, C: {pfc['C']}\n------------------")
    
    # 3つの栄養素がすべて0の場合は、解析失敗とみなす
    if pfc['P'] == 0.0 and pfc['F'] == 0.0 and pfc['C'] == 0.0:
        raise ValueError("PFCの値をテキストから抽出できませんでした。")
        
    return pfc


def calculate_ratio_from_parsed(parsed_pfc):
    """
    解析済みのPFC辞書からカロリーベースのPFC比率を計算する。
    """
    # 各栄養素のグラムあたりのカロリー
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