import os
import requests
import logging
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, PostbackEvent
from linebot.exceptions import LineBotApiError
from flask import Flask, request, abort

app = Flask(__name__)

# 商品字典
product_dict = {
    '30': '531',
    '60': '532',
    '90': '533',
    '120': '534',
    '150': '535',
    '180': '536',
    '210': '537',
    '240': '538'
}

user_state = {}

line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))

# 設定 API key
API_KEY = os.environ.get("API_KEY")

@app.route("/line_callback", methods=['POST'])
def line_callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        print(e)
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    message = event.message.text
    if message == '下單':
        # 啟動下單流程
        state = ask_order_time(event)
        # 設定使用者的狀態為「處理下單」
        user_state[user_id] = state
    else:
        if user_id in user_state and user_state[user_id] == 'handle_order_time_response':
            # 當使用者已經輸入下單需要的時間，就詢問使用者商品的直播網址
            product_id = product_dict.get(message)
            if product_id:
                # 如果商品存在，詢問商品的直播網址
                user_state[user_id] = ('handle_link_response', product_id, '', message)
                ask_link(event, message)
            else:
                # 如果商品不存在，提示使用者重新輸入下單需要的時間
                reply_message = TextSendMessage(text='輸入的時間不正確，請重新輸入下單需要的時間：30 / 60 / 90 / 120 / 150 / 180 / 210 / 240')
                line_bot_api.reply_message(event.reply_token, reply_message)
        elif user_id in user_state and user_state[user_id][0] == 'handle_link_response':
            # 當使用者已經輸入商品的直播網址，就詢問使用者商品數量
            state = handle_link_response(event, user_state[user_id][1], '', user_state[user_id][3], message)

            user_state[user_id] = state
        elif user_id in user_state and user_state[user_id][0] == 'handle_order_quantity':
            # 當使用者已經輸入商品數量，就進行下單
            handle_order_quantity(event, *user_state[user_id][1:])
            # 下單完成後，清空使用者狀態
            del user_state[user_id]
        else:
            # 無法辨識的訊息
            reply_message = TextSendMessage(text='抱歉，我不了解您的意思，請輸入「下單」來開始下單流程。')
            line_bot_api.reply_message(event.reply_token, reply_message)
            # 設定使用者的狀態為「處理下單」
            user_state[event.source.user_id] = 'handle_order_time_response'
            # 詢問使用者下單需要的時間
            ask_order_time(event)
def ask_order_time(event):
    reply_message = TextSendMessage(text='請輸入直播時長(分鐘)：\n30 / 60 / 90 / 120 / 150 / 180 / 210 / 240')
    line_bot_api.reply_message(event.reply_token, reply_message)
    return 'handle_order_time_response'

def ask_link(event, product_id):
    reply_message = TextSendMessage(text=f'請提供時長{product_id}分鐘的直播網址：')
    line_bot_api.reply_message(event.reply_token, reply_message)

def handle_link_response(event, product_id, link, product_name, message):
    # 取得使用者輸入的直播網址
    link = message
    # 詢問使用者商品數量
    ask_quantity(event, product_name)
    return 'handle_order_quantity', product_id, link, product_name

def ask_quantity(event, product_name):
    reply_message = TextSendMessage(text=f'請輸入下單人數：')
    line_bot_api.reply_message(event.reply_token, reply_message)

def handle_order_quantity(event, product_id, link, product_name):
    # 取得使用者輸入的商品數量
    quantity = event.message.text
    # 向 API 發送下單的請求
    url = 'https://fbliveviewerbot.com/api/v2'
    payload = {'key': API_KEY, 'action': 'add', 'service': product_id, 'quantity': quantity, 'link': link}
    response = requests.post(url, data=payload)
    # 解析 API 回傳的 JSON 資料
    data = response.json()
    if 'order' in data:
        order_id = data['order']
        # 向 API 發送查詢餘額的請求
        url = 'https://fbliveviewerbot.com/api/v2'
        payload = {'key': API_KEY, 'action': 'balance'}
        response = requests.post(url, data=payload)
        # 解析 API 回傳的 JSON 資料
        data = response.json()
        if 'balance' in data:
            balance = data['balance']
            currency = data['currency']
            reply_message = f'已下單成功，訂單編號為 {order_id}，您的餘額為 {balance} {currency}'
        else:
            reply_message = f'已下單成功，訂單編號為 {order_id}，但無法取得餘額資訊'
    else:
        reply_message = '下單失敗，請稍後再試'
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))
# 設定 Line bot 的 Webhook URL，讓 Line 可以將使用者訊息傳送到這個網址
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except LineBotApiError as e:
        print(e)
        abort(400)
    return 'OK'

if __name__ == "__main__":
    app.run()
