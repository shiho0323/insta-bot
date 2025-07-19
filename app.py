import os
from flask import Flask, request, abort
import requests
from dotenv import load_dotenv
import json
import traceback
import pytesseract

# --- 【重要】Render環境でTesseractの場所を明示的に指定 ---
# DockerfileでインストールしたTesseractへのパスを念のため指定しておきます。
# これにより環境による差異を吸収します。
if os.path.exists('/usr/bin/tesseract'):
    pytesseract.pytesseract.tesseract_cmd = r'/usr/bin/tesseract'


# --- OCR関数の定義（安全なフォールバック方式） ---
# 次に、実際のモジュールのインポートを試みます。
# 成功すれば、上のダミー関数が実際の関数で上書きされます。

from ocr_module import ocr_from_bytes, robust_parse_pfc, calculate_ratio_from_parsed 
#print(">>> Successfully imported 'ocr_module'.", flush=True)

# --- ここからFlaskアプリ本体 ---

load_dotenv()
app = Flask(__name__)
VERIFY_TOKEN      = os.getenv('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GRAPH_API_URL     = 'https://graph.facebook.com/v20.0'

@app.route('/webhook', methods=['GET'])
def verify():
    mode = request.args.get('hub.mode')
    token = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        print(">>> Webhook verification successful!", flush=True)
        return challenge, 200
    print(">>> Webhook verification failed.", flush=True)
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
                print(f">>> Resolving media_id {media_id} to a URL...", flush=True)
                graph_api_url = f"{GRAPH_API_URL}/{media_id}"
                params = {'fields': 'media_url', 'access_token': PAGE_ACCESS_TOKEN}
                res = requests.get(graph_api_url, params=params)
                res.raise_for_status()
                media_url = res.json().get('media_url')

            if not media_url:
                print(">>> No media URL found or resolved, skipping attachment.", flush=True)
                continue

            print(f">>> Downloading image from: {media_url}", flush=True)
            img_response = requests.get(media_url)
            img_response.raise_for_status()
            img_bytes = img_response.content

            # 1. 画像からテキストを抽出
            extracted_text = ocr_from_bytes(img_bytes)
            print(f">>> OCR Result: \n{extracted_text}", flush=True) # 抽出結果をログに出力

            # 2. テキストを解析してPFCの数値を取得
            parsed_data = robust_parse_pfc(extracted_text)

            # 3. 解析データからPFC比率を計算
            ratio = calculate_ratio_from_parsed(parsed_data)

            reply_text = f"PFCバランスを計算しました！\nP: {ratio['P']:.1f}%\nF: {ratio['F']:.1f}%\nC: {ratio['C']:.1f}%"
            send_message(sender_id, reply_text)

        except Exception as e:
            print("!!!!!!!!!! ERROR PROCESSING ONE ATTACHMENT !!!!!!!!!!", flush=True)
            print(f"Exception: {repr(e)}", flush=True)
            traceback.print_exc()
            print(f"Problematic Attachment Data: {att}", flush=True)
            send_message(sender_id, "添付ファイルの処理中にエラーが発生しました。")

def send_message(recipient_id, text):
    print(f">>> Sending message to {recipient_id}: {text}", flush=True)
    params = {'access_token': PAGE_ACCESS_TOKEN}
    json_data = {'recipient': {'id': recipient_id}, 'message': {'text': text}, 'messaging_type': 'RESPONSE'}
    try:
        response = requests.post(f"{GRAPH_API_URL}/me/messages", params=params, json=json_data)
        response.raise_for_status()
        print(">>> Reply sent successfully.", flush=True)
    except requests.exceptions.RequestException as e:
        print(f">>> Error sending reply message: {e}", flush=True)
        if isinstance(e, requests.exceptions.HTTPError) and e.response.status_code == 400:
            print(">>> A '400 Bad Request' error suggests a problem with the request itself or permissions.", flush=True)
            print(">>> Please check: 1. Page Access Token validity. 2. App permissions (instagram_manage_messages). 3. API version compatibility.", flush=True)
        if 'response' in locals() and response:
            print(">>> Response body:", response.text, flush=True)

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    print(">>> FULL PAYLOAD:\n", json.dumps(data, indent=2, ensure_ascii=False), flush=True)

    if data.get('object') != 'instagram':
        return 'Ignored: Not an Instagram event', 200

    for entry in data.get('entry', []):
        for ev in entry.get('messaging', []):
            try:
                sender_id = ev.get('sender', {}).get('id')
                if not sender_id:
                    print(f">>> Skipping event, cannot determine sender: {ev}", flush=True)
                    continue

                if 'message' in ev:
                    message = ev['message']
                    if message.get('is_echo'):
                        continue
                    
                    if message.get('is_deleted'):
                        print(f">>> Received a message deletion notification from {sender_id}. MID: {message.get('mid')}", flush=True)
                        continue

                    if 'attachments' in message:
                        process_image_attachments(message['attachments'], sender_id)
                    elif 'text' in message:
                        print(f">>> Received text from {sender_id}: {message['text']}", flush=True)
                elif 'read' in ev or 'delivery' in ev:
                    event_type = 'read' if 'read' in ev else 'delivery'
                    print(f">>> Received {event_type} receipt from {sender_id}. Skipping.", flush=True)
                else:
                    print(f">>> Received unknown event type from {sender_id}: {list(ev.keys())}", flush=True)

            except Exception as e:
                print("!!!!!!!!!! ERROR PROCESSING ONE EVENT !!!!!!!!!!", flush=True)
                print(f"Exception: {repr(e)}", flush=True)
                traceback.print_exc()
                print(f"Problematic Event Data: {ev}", flush=True)
                print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", flush=True)
                continue

    return 'OK', 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.getenv('PORT', 5000))