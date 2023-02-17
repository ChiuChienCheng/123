import os

from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError, LineBotApiError
from linebot.models import MessageEvent, TextMessage, TextSendMessage

from flask import Flask, request, abort


user_state = {}
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


# 访问 CHANNEL_ACCESS_TOKEN 环境变量
line_bot_api = LineBotApi(os.environ.get("CHANNEL_ACCESS_TOKEN"))

# 访问 CHANNEL_SECRET 环境变量
handler = WebhookHandler(os.environ.get("CHANNEL_SECRET"))


# 設定 API key
API_KEY = os.environ.get("API_KEY")

app = Flask(__name__)


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

    if user_id in user_state and user_state[user_id][0] == 'handle_order_time_response':
        # 当用户已经输入下单需要的时间，就询问用户商品的直播网址
        product_id = product_dict.get(message)
        if product_id:
            # 如果商品存在，询问商品的直播网址
            user_state[user_id] = ('handle_link_response', product_id, '', message)
            ask_link(event, message)
        else:
            # 如果商品不存在，提示用户重新输入下单需要的时间
            reply_message = TextSendMessage(text='輸入的時間不正確，請重新輸入下單需要的時間：30 / 60 / 90 / 120 / 150 / 180 / 210 / 240')
            line_bot_api.reply_message(event.reply_token, reply_message)
            return

    if message != '下單':
        # 如果用户没有发送 "下单"，则直接回复提示消息
        reply_message = TextSendMessage(text='抱歉，我不了解您的意思，請輸入「下單」來開始下單流程。')
        line_bot_api.reply_message(event.reply_token, reply_message)
        # 設定使用者的狀態為「處理下單」
        user_state[event.source.user_id] = 'handle_order_time_response'
        # 詢問使用者下單需要的時間
        ask_order_time(event)
    else:
        # 啟動下單流程
        state = ask_order_time(event)
        # 設定使用者的狀態為「處理下單」
        user_state[user_id] = state
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
    # 確認資料是否正確
    user_id = event.source.user_id
    user_state[user_id] = ('confirm_order', product_id, link, product_name, quantity)
    confirm_order(event, product_id, link, product_name, quantity)

def confirm_order(event, product_id, link, product_name, quantity):
    # 確認使用者資料是否正確
    message = f'請確認您所要下單的資料：\n\n商品：{product_name}\n網址：{link}\n數量：{quantity}\n\n輸入 "確認" 確認訂單，輸入 "取消" 取消訂單。'
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=message))

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    message = event.message.text

if user_id in user_state and user_state[user_id][0] == 'confirm_order':
    # 如果正在确认订单信息，根据用户的回复执行相应的操作
    if message == '是':
        # 用户确认下单信息，向 API 发送下单请求
        product_id, link, product_name, quantity = user_state[user_id][1:]
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
        user_state[user_id] = None
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_message))
    elif message == '否':
        # 用户取消下单，重置用户状态
        user_state[user_id] = None
        reply_message = TextSendMessage(text='已取消下單。')
        line_bot_api.reply_message(event.reply_token, reply_message)

# 重置用户状态
user_state[user_id] = None
# 回复用户下单结果
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
