def send_telegram_notify(token: str, chat_id: str, message: str):
    import requests
    telegram_url = f'https://api.telegram.org/bot{token}/sendMessage'
    header = {"Content-type": "application/x-www-form-urlencoded", "Accept": "text/plain"}
    _ = requests.post(telegram_url, params={'chat_id': chat_id, 'text': message}, headers=header)


def send_line_notify(token: str, message: str):
    from line_notify import LineNotify
    notify = LineNotify(token)
    notify.send(message)


def trade_bot(request):
    """Responds to any HTTP request.
    Args:
        request (flask.Request): HTTP request object.
    Returns:
        The response text or any set of values that can be turned into a
        Response object using
        `make_response <http://flask.pocoo.org/docs/1.0/api/#flask.Flask.make_response>`.

        {
          "binance_key": "xxxxxx",
          "binance_secret": "xxxxxxxxxx",
          "line_token": "xxxxxxx",
          "telegram_token": "xxxxxxx",
          "telegram_chat_id": "xxxxxx",
          "binance_action": "buy",
          "binance_symbol": "BTCUSDT",
          "binance_asset_name": "USDT",
          "binance_asset_amount": "0"
        }

    """
    request_json = request.get_json()

    print(request_json)
    if request_json and 'binance_key' in request_json:

        from binance.client import Client
        from binance.exceptions import BinanceAPIException
        import math

        line_notify_flag = False
        telegram_notify_flag = False

        binance_key = request_json['binance_key']
        binance_secret = request_json['binance_secret']
        line_token = request_json['line_token']
        telegram_token = request_json['telegram_token']
        telegram_chat_id = request_json['telegram_chat_id']
        binance_action = request_json['binance_action']
        binance_symbol = request_json['binance_symbol']
        binance_asset_name = request_json['binance_asset_name']
        binance_asset_amount = request_json['binance_asset_amount']

        if not (line_token and line_token.strip()):
            line_notify_flag = False
        else:
            line_notify_flag = True

        if not (telegram_token and telegram_token.strip()):
            telegram_notify_flag = False
        else:
            telegram_notify_flag = True
            if not (telegram_chat_id and telegram_chat_id.strip()):
                return "Incomplete"

        if not (binance_key and binance_key.strip()):
            return "Incomplete"

        if not (binance_secret and binance_secret.strip()):
            return "Incomplete"

        if not (binance_action and binance_action.strip()):
            return "Incomplete"

        if not (binance_symbol and binance_symbol.strip()):
            return "Incomplete"

        if not (binance_asset_name and binance_asset_name.strip()):
            return "Incomplete"

        if not (binance_asset_amount and binance_asset_amount.strip()):
            binance_asset_amount = 0.0
        else:
            binance_asset_amount = float(binance_asset_amount)

        if binance_action not in ('buy', 'sell'):
            return "No action"

        # Get current balance
        binance_client = Client(binance_key, binance_secret)
        balance = binance_client.get_asset_balance(asset=binance_asset_name)
        print(f"Available Balance: {balance['free']} {binance_asset_name}")

        # Get last price of symbol
        symbol_price = binance_client.get_symbol_ticker(symbol=binance_symbol)
        print(f"Last price for {binance_symbol} is {symbol_price['price']} {binance_asset_name}")

        print(f"Action: {binance_action}")
        if binance_action == 'buy':

            # balance['free'] = 200
            # Calculate commission fee (1%)
            if float(binance_asset_amount) < 1.0:
                # All in Buy
                balance_after_fee = float(balance['free']) - (float(balance['free']) * 0.005)
            else:
                print(f"Asset amount: {binance_asset_amount}")
                print(f"Available Balance: {balance['free']}")
                if float(balance['free']) < float(binance_asset_amount):
                    notify_text = f"Insufficient balance to buy Symbol: {binance_symbol} with {binance_asset_name} available balance: {balance['free']} specific balance: {binance_asset_amount}"
                    if line_notify_flag:
                        send_line_notify(token=line_token, message=notify_text)

                    if telegram_notify_flag:
                        send_telegram_notify(token=telegram_token, chat_id=telegram_chat_id, message=notify_text)

                    print(notify_text)
                    return "done"

                balance_after_fee = float(binance_asset_amount) - (float(binance_asset_amount) * 0.005)
                print(f"Balance after fee: {balance_after_fee}")

            qty = float(balance_after_fee) / float(symbol_price['price'])
            decimals = 6
            if binance_symbol == "ETHUSDT":
                decimals = 5

            multiplier = 10 ** decimals
            buy_qty = math.floor(qty * multiplier) / multiplier

            print(f"Buy {binance_symbol} with {binance_asset_name} amount: {balance_after_fee} will get qty = {buy_qty} {binance_symbol}")

            if float(buy_qty) < 0.00001 or balance_after_fee < 10:
                # Minimum buy QTY = 0.00001
                notify_text = f"Insufficient balance to buy Symbol: {binance_symbol} with {binance_asset_name} balance: {balance_after_fee} Price: {symbol_price['price']} Qty: {buy_qty} ({qty})"
                if line_notify_flag:
                    send_line_notify(token=line_token, message=notify_text)

                if telegram_notify_flag:
                    send_telegram_notify(token=telegram_token, chat_id=telegram_chat_id, message=notify_text)

                print(notify_text)
                return "done"

            # Place Buy Order
            try:
                order = binance_client.order_market_buy(symbol=binance_symbol, quantity=float(buy_qty))
                notify_text = f"Order Buy Symbol: {binance_symbol} Balance: {balance_after_fee} {binance_asset_name} Price: {symbol_price['price']} Qty: {buy_qty} ({qty}) Order detail: {order}"
            except BinanceAPIException as bi_ex:
                notify_text = f"Error {bi_ex.message} Buy symbol: {binance_symbol} Balance: {balance_after_fee} {binance_asset_name} Price: {symbol_price['price']} Qty: {buy_qty} ({qty})"

            print(notify_text)

            if line_notify_flag:
                send_line_notify(token=line_token, message=notify_text)

            if telegram_notify_flag:
                send_telegram_notify(token=telegram_token, chat_id=telegram_chat_id, message=notify_text)

        if binance_action == 'sell':
            # Place Sell Order
            if float(balance['free']) > 0.00001:
                try:
                    if float(binance_asset_amount) < 1.0:
                        # All out sell
                        qty = float(balance['free'])
                    else:
                        qty = float(binance_asset_amount)

                    decimals = 6
                    if binance_symbol == "ETHUSDT":
                        decimals = 5

                    multiplier = 10 ** decimals
                    sell_qty = math.floor(qty * multiplier) / multiplier

                    order = binance_client.order_market_sell(symbol=binance_symbol, quantity=float(sell_qty))
                    notify_text = f"Sell Symbol: {binance_symbol} Price: {symbol_price['price']} Qty: {sell_qty} ({qty}) for asset {binance_asset_name} Order detail: {order}"

                except BinanceAPIException as bi_ex:
                    notify_text = f"Error {bi_ex.message} Sell symbol: {binance_symbol} Price: {symbol_price['price']} qty: {sell_qty} ({qty}) for asset {binance_asset_name}"
            else:
                notify_text = f"Error asset {binance_asset_name} not enough to sell {binance_symbol} qty: {binance_asset_amount}, current balance: {balance['free']} {binance_asset_name}"

            print(notify_text)

            if line_notify_flag:
                send_line_notify(token=line_token, message=notify_text)

            if telegram_notify_flag:
                send_telegram_notify(token=telegram_token, chat_id=telegram_chat_id, message=notify_text)

    return "done"
