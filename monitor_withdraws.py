import asyncio
import websockets
import requests
import graphql_subscriptions
import json
import os
from datetime import datetime
from exchange_rate_utils import fetch_exchange_rate
from user_info_utils import get_coins

cookie = os.environ['SESSION_COOKIE']
async def monitor_withdraw(min_price=10, liquidity=0.74, _ratio=0):
    # Color codes
    COLOR_RED = "\033[91m"
    COLOR_GREEN = "\033[92m"
    COLOR_RESET = "\033[0m"
    USD = fetch_exchange_rate()
    max_price = 5000
    print(f"Exchange Rate: {USD}, Min Price: {min_price}, Liquidity: {liquidity}, Ratio: {_ratio}\n")

    buff_prices = requests.get('https://raw.githubusercontent.com/ScottyPoon/buff-prices/main/buff_prices.json',
                               headers={'Authorization': 'Token ' + os.environ['HUB_TOKEN']}).json()

    buff_prices = {k: v['price'] for k, v in buff_prices.items()
                   if min_price * 0.5 <= v['price'] <= max_price
                   and float(buff_prices[k]['liquidity']) >= liquidity}
    buff_price_rmb = {name: round(price * USD, 2) for name, price in buff_prices.items()}

    while True:
        async with websockets.connect('wss://api.{}.com/graphql'.format(os.environ['DOMAIN']),
                                      subprotocols=['graphql-transport-ws'],
                                      ) as websocket:

            try:
                await websocket.send('{"type": "connection_init"}')

                await graphql_subscriptions.subscribe_to_create_trade(websocket)
                while True:
                    response = json.loads(await websocket.recv())
                    try:
                        trade_info = response['payload']['data']['createTrade']['trade']
                        print(trade_info)
                        roll_price = trade_info['totalValue']
                        if not (min_price <= roll_price <= max_price):
                            continue

                        name = trade_info['tradeItems'][0]['marketName']

                        buff_price = buff_price_rmb.get(name)
                        if buff_price is None:
                            continue

                        ratio = buff_price / roll_price
                        print(ratio)
                        if ratio >= _ratio:
                            current_time = datetime.now()
                            created_at = datetime.strptime(trade_info['createdAt'], "%Y-%m-%dT%H:%M:%S.%fZ")
                            time_difference = (current_time - created_at).total_seconds() * 1000
                            markup_percent = trade_info['markupPercent']
                            float_value = trade_info.get('avgPaintWear', "")
                            print(
                                f"[{created_at.strftime('%H:%M:%S.%f')[:-3]}] {COLOR_GREEN}{ratio:.2f} {name} {float_value} roll: {roll_price:.2f} buff: {buff_price:.2f} {markup_percent} withdraw {current_time.strftime('%H:%M:%S.%f')[:-3]} {int(time_difference)}ms{COLOR_RESET}")

                    except KeyError:
                        error_message = response.get('payload', {}).get('errors', [{}])[0].get('message')
                        if error_message:
                            print(f'[{datetime.now().strftime("%H:%M:%S.%f")[:-3]}] {error_message}')
                        if error_message == "This withdrawal exceeds your daily withdrawal limit":
                            print("Quitting Program")
                            return

            except websockets.exceptions.ConnectionClosed:
                pass
            except Exception as e:
                print('The Exception in last line is', e)