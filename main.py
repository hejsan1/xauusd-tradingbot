import os
import json
import time
import urllib.request
import urllib.parse
import urllib.error

BASE = "https://demo.tradelocker.com/backend-api"
ACCOUNT_ID = "2656810"

def log(*args):
    print(*args, flush=True)

def api(path, headers=None, data=None):
    if data is not None and path != "/auth/jwt/token":
        raise ValueError("POST BLOCKED")

    request = urllib.request.Request(
        BASE + path,
        headers=headers or {},
        data=data,
        method="POST" if data is not None else "GET"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)
def build_order(instrument_id, route_id,
                side, quantity, sl, tp):

    if side not in ("buy", "sell"):
        raise ValueError("Invalid side")

    if quantity <= 0:
        raise ValueError("Invalid quantity")

    return {
        "tradableInstrumentId": int(instrument_id),
        "routeId": int(route_id),
        "side": side,
        "type": "market",
        "validity": "IOC",
        "qty": quantity,
        "price": 0,
        "stopLoss": sl,
        "stopLossType": "absolute",
        "takeProfit": tp,
        "takeProfitType": "absolute",
        "strategyId": "EMA_RSI"
    }
def main():
    log("ASH ACCOUNT - READ ONLY")
    log("CHECKING XAUUSD SPECIFICATIONS")

    if os.environ.get("TL_ENVIRONMENT", "").lower() != "demo":
        raise ValueError("Only DEMO allowed")

    credentials = {
        "email": os.environ["TL_EMAIL"],
        "password": os.environ["TL_PASSWORD"],
        "server": os.environ["TL_SERVER"]
    }

    auth = api(
        "/auth/jwt/token",
        {"Content-Type": "application/json"},
        json.dumps(credentials).encode()
    )

    headers = {
        "Authorization": "Bearer " + auth["accessToken"]
    }

    log("LOGIN SUCCESSFUL")

    accounts = api(
        "/auth/jwt/all-accounts",
        headers
    )["accounts"]

    account = next(
        a for a in accounts
        if str(a["id"]) == ACCOUNT_ID
    )

    headers["accNum"] = str(account["accNum"])

    log("CORRECT ASH ACCOUNT FOUND")

    instruments = api(
        f"/trade/accounts/{ACCOUNT_ID}/instruments",
        headers
    )["d"]["instruments"]

    gold = next(
        i for i in instruments
        if i["name"].upper() == "XAUUSD"
    )

    route = next(
        r for r in gold["routes"]
        if r["type"] == "TRADE"
    )

    instrument_id = gold["tradableInstrumentId"]

    query = urllib.parse.urlencode({
        "routeId": route["id"]
    })

    spec = api(
        f"/trade/instruments/{instrument_id}?{query}",
        headers
    )["d"]

    log("------------------------")
    log("XAUUSD SPECIFICATIONS")

    for key in [
        "lotSize",
        "lotStep",
        "minLot",
        "maxLot",
        "tickSize",
        "tickCost",
        "leverage",
        "quotingCurrency",
        "symbolStatus",
        "barSource"
    ]:
        log(key, ":", spec.get(key))

    log("------------------------")
    log("SPECIFICATION TEST COMPLETE")
    log("READ ONLY - NO ORDERS")

try:
    main()

except urllib.error.HTTPError as error:
    log("HTTP ERROR:", error.code)

except KeyError as error:
    log("MISSING FIELD:", error)

except Exception as error:
    log("ERROR:", type(error).__name__)

while True:
    time.sleep(60)
