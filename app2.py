# app.py
import os
from flask import Flask, request, abort
import requests
from dotenv import load_dotenv
from ocr_module import ocr_from_bytes, robust_parse_pfc, calculate_ratio_from_parsed

load_dotenv()
app = Flask(__name__)
VERIFY_TOKEN      = os.getenv('VERIFY_TOKEN')
PAGE_ACCESS_TOKEN = os.getenv('PAGE_ACCESS_TOKEN')
GRAPH_API_URL     = 'https://graph.facebook.com/v15.0'

@app.route('/webhook', methods=['GET'])
def verify():
    mode      = request.args.get('hub.mode')
    token     = request.args.get('hub.verify_token')
    challenge = request.args.get('hub.challenge')
    # ここでログ出力
    print(">>> VERIFY REQ:", {
        'mode': mode,
        'token': token,
        'challenge': challenge
    })
    if mode == 'subscribe' and token == VERIFY_TOKEN:
        return challenge, 200
    return 'Forbidden', 403

# --- DMイベント受信用エンドポイント (POST) ---
@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.get_json()
    import json
    print(">>> FULL PAYLOAD:\n", json.dumps(data, indent=2, ensure_ascii=False))
    return 'OK', 200
    
    if data.get('object') != 'instagram':
        return 'Ignored', 200

    for entry in data.get('entry', []):
        for ev in entry.get('messaging', []):
            # 安全に取り出し
            attachments = ev.get('message', {}).get('attachments', [])
            print(">>> RAW ATTACHMENTS LIST:", attachments)

            for att in attachments:
                # まずは att 自体をそのままプリント（辞書アクセスせず）
                print(">>> ONE ATTACHMENT RAW:", att)

                if att.get('type') != 'image':
                    continue

                payload = att.get('payload', {})
                media_url = None

                # payload の中身を安全に検査
                if 'id' in payload:
                    # Facebook 経由のときは ID から media_url を取る
                    media_id = payload['id']
                    res = requests.get(
                        f"{GRAPH_API_URL}/{media_id}",
                        params={
                            'fields': 'media_url',
                            'access_token': PAGE_ACCESS_TOKEN
                        }
                    ).json()
                    media_url = res.get('media_url')
                elif 'url' in payload:
                    # Instagram Messaging では最初から URL が来る
                    media_url = payload.get('url')

                if not media_url:
                    print(">>> No media URL found, skipping this attachment")
                    continue

                # ここでようやく画像をダウンロード
                img_bytes = requests.get(media_url).content

                # OCR→解析→返信
                text   = ocr_from_bytes(img_bytes)
                parsed = robust_parse_pfc(text)
                ratio  = calculate_ratio_from_parsed(parsed)

                reply = f"P:{ratio['P']:.1f}% / F:{ratio['F']:.1f}% / C:{ratio['C']:.1f}% です！"
                requests.post(
                    f"{GRAPH_API_URL}/me/messages",
                    params={'access_token': PAGE_ACCESS_TOKEN},
                    json={'recipient': {'id': sender_id}, 'message': {'text': reply}}
                )
    return 'OK', 200


if __name__ == '__main__':
    # 全インターフェース(IPv4/IPv6)でリッスン
    app.run(host='0.0.0.0', port=5000)
