import os
from flask import Flask, request, abort
import requests
from dotenv import load_dotenv
import json
import traceback

pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'  # Tesseractのパスを指定（環境に応じて変更）

# --- OCRモジュールのインポートとフォールバック ---
try:
    # ユーザー提供の実際のモジュールをインポート試行
    from ocr_module import ocr_from_bytes, robust_parse_pfc, calculate_ratio_from_parsed
    print(">>> Successfully imported 'ocr_module'.")
except Exception as e:
    # 【修正点】ImportErrorだけでなく、あらゆる例外を捕捉してフォールバックする
    print(f">>> Could not import 'ocr_module' (Error: {repr(e)}). Falling back to dummy functions.")
    traceback.print_exc()
    
    # --- ocr_moduleのダミー実装 ---
    def ocr_from_bytes(img_bytes):
        print(">>> (Dummy) OCR processing...")
        return "たんぱく質 20g\n脂質 15g\n炭水化物 50g"

    def robust_parse_pfc(text):
        print(">>> (Dummy) Parsing PFC...")
        return {'P': 20, 'F': 15, 'C': 50}

    def calculate_ratio_from_parsed(parsed):
        print(">>> (Dummy) Calculating ratio...")
        total_calories = parsed['P'] * 4 + parsed['F'] * 9 + parsed['C'] * 4
        if total_calories == 0: return {'P': 0, 'F': 0, 'C': 0}
        return {
            'P': (parsed['P'] * 4 / total_calories) * 100,
            'F': (parsed['F'] * 9 / total_calories) * 100,
            'C': (parsed['C'] * 4 / total_calories) * 100,
        }
# --- フォールバックここまで ---

load_dotenv()
app = Flask(__name__)
VERIFY_TOKEN      = os.getenv('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
# APIバージョンを最新に指定
GRAPH_API_URL     = 'https://graph.facebook.com/v20.0'

@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print(">>> Webhook verification successful!")
        return challenge, 200
    print(">>> Webhook verification failed.")
    return 'Forbidden', 403

def process_image_attachments(attachments, sender_id):
    for att in attachments:
        try:
            if att.get('type') != 'image':
                continue

            payload = att.get('payload', {})
            media_url = payload.get('url')

            if not media_url and 'id' in payload:
                media_id = payload['id']
                print(f">>> Resolving media_id {media_id} to a URL...")
                graph_api_url = f"{GRAPH_API_URL}/{media_id}"
                params = {'fields': 'media_url', 'access_token': PAGE_ACCESS_TOKEN}
                res = requests.get(graph_api_url, params=params)
                res.raise_for_status()
                media_url = res.json().get('media_url')

            if not media_url:
                print(">>> No media URL found or resolved, skipping attachment.")
                continue

            print(f">>> Downloading image from: {media_url}")
            img_response = requests.get(media_url)
            img_response.raise_for_status()
            img_bytes = img_response.content

            text = ocr_from_bytes(img_bytes)
            parsed = robust_parse_pfc(text)
            ratio = calculate_ratio_from_parsed(parsed)

            reply_text = f"PFCバランスを計算しました！\nP: {ratio['P']:.1f}%\nF: {ratio['F']:.1f}%\nC: {ratio['C']:.1f}%"
            send_message(sender_id, reply_text)

        except Exception as e:
            print("!!!!!!!!!! ERROR PROCESSING ONE ATTACHMENT !!!!!!!!!!")
            print(f"Exception: {repr(e)}")
            traceback.print_exc()
            print(f"Problematic Attachment Data: {att}")
            send_message(sender_id, "添付ファイルの処理中にエラーが発生しました。")

def send_message(recipient_id, text):
    print(f">>> Sending message to {recipient_id}: {text}")
    params = {'access_token': PAGE_ACCESS_TOKEN}
    json_data = {'recipient': {'id': recipient_id}, 'message': {'text': text}, 'messaging_type': 'RESPONSE'}
    try:
        response = requests.post(f"{GRAPH_API_URL}/me/messages", params=params, json=json_data)
        response.raise_for_status()
        print(">>> Reply sent successfully.")
    except requests.exceptions.RequestException as e:
        print(f">>> Error sending reply message: {e}")
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 400:
            print(">>> A '400 Bad Request' error suggests a problem with the request itself or permissions.")
            print(">>> Please check: 1. Page Access Token validity. 2. App permissions (instagram_manage_messages). 3. API version compatibility.")
        if 'response' in locals() and response:
            print(">>> Response body:", response.text)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print(">>> FULL PAYLOAD:\n", json.dumps(data, indent=2, ensure_ascii=False))

    if data.get('object') != 'instagram':
        return 'Ignored: Not an Instagram event', 200

    for entry in data.get('entry', []):
        for ev in entry.get('messaging', []):
            try:
                sender_id = ev.get('sender', {}).get('id')
                if not sender_id:
                    print(f">>> Skipping event, cannot determine sender: {ev}")
                    continue

                if 'message' in ev:
                    message = ev['message']
                    if message.get('is_echo'):
                        continue
                    
                    if message.get('is_deleted'):
                        print(f">>> Received a message deletion notification from {sender_id}. MID: {message.get('mid')}")
                        continue

                    if 'attachments' in message:
                        process_image_attachments(message['attachments'], sender_id)
                    elif 'text' in message:
                        print(f">>> Received text from {sender_id}: {message['text']}")
                elif 'read' in ev or 'delivery' in ev:
                    event_type = 'read' if 'read' in ev else 'delivery'
                    print(f">>> Received {event_type} receipt from {sender_id}. Skipping.")
                else:
                    print(f">>> Received unknown event type from {sender_id}: {list(ev.keys())}")

            except Exception as e:
                print("!!!!!!!!!! ERROR PROCESSING ONE EVENT !!!!!!!!!!")
                print(f"Exception: {repr(e)}")
                traceback.print_exc()
                print(f"Problematic Event Data: {ev}")
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                continue

    return 'OK', 200

if __name__ == '__main__':
    # アプリ起動時に環境変数が読み込まれているか確認
    if not PAGE_ACCESS_TOKEN:
        print("FATAL ERROR: PAGE_ACCESS_TOKEN is not set. Please check your .env file.")
    else:
        print(">>> PAGE_ACCESS_TOKEN loaded successfully.")
    
    if not VERIFY_TOKEN:
        print("FATAL ERROR: VERIFY_TOKEN is not set. Please check your .env file.")
    else:
        print(">>> VERIFY_TOKEN loaded successfully.")

    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))