
import os
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone

BASE = "https://demo.tradelocker.com/backend-api"
ACCOUNT_ID = "2656810"
INTERVAL = 30


def api(path, headers=None, data=None):
    if data is not None and path != "/auth/jwt/token":
        raise ValueError("Only read access allowed")

    request = urllib.request.Request(
        BASE + path,
        headers=headers or {},
        data=data,
        method="POST" if data is not None else "GET"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def connect():
    if os.environ["TL_ENVIRONMENT"].lower() != "demo":
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

    accounts = api(
        "/auth/jwt/all-accounts", headers
    )["accounts"]

    account = next(
        (a for a in accounts
         if str(a["id"]) == ACCOUNT_ID),
        None
    )

    if account is None:
        raise ValueError("Target account not found")

    headers["accNum"] = str(account["accNum"])

    config = api("/trade/config", headers)["d"]
    columns = config["accountDetailsConfig"]["columns"]

    instruments = api(
        f"/trade/accounts/{ACCOUNT_ID}/instruments",
        headers
    )["d"]["instruments"]

    gold = next(
        (i for i in instruments
         if i["name"].upper() == "XAUUSD"),
        None
    )

    if gold is None:
        raise ValueError("XAUUSD not found")

    route = next(
        r for r in gold["routes"]
        if r["type"] == "INFO"
    )

    params = {
        "routeId": route["id"],
        "tradableInstrumentId": gold["tradableInstrumentId"]
    }

    print("LOGIN SUCCESSFUL", flush=True)
    print("CORRECT ACCOUNT FOUND", flush=True)
    print("XAUUSD FOUND", flush=True)

    return headers, columns, params


def get_candles(headers, params, minutes):
    now = int(time.time() * 1000)
    duration = minutes * 60 * 1000

    query = urllib.parse.urlencode({
        **params,
        "resolution": f"{minutes}m",
        "from": now - 7 * 24 * 60 * 60 * 1000,
        "to": now
    })

    result = api("/trade/history?" + query, headers)

    if result.get("s") != "ok":
        return []

    bars = result.get("d", {}).get("barDetails", [])

    closed = {
        int(b["t"]): float(b["c"])
        for b in bars
        if int(b["t"]) + duration <= now
    }

    return sorted(closed.items())


def ema(values, period):
    result = sum(values[:period]) / period
    multiplier = 2 / (period + 1)

    for value in values[period:]:
        result = value * multiplier + result * (1 - multiplier)

    return result


def rsi(values, period=14):
    changes = [
        values[i] - values[i - 1]
        for i in range(1, len(values))
    ]

    gains = [max(x, 0) for x in changes]
    losses = [max(-x, 0) for x in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for gain, loss in zip(gains[period:], losses[period:]):
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period

    if avg_loss == 0:
        return 50 if avg_gain == 0 else 100

    return 100 - 100 / (1 + avg_gain / avg_loss)


def analyze(bars, minutes):
    if len(bars) < 100:
        return None

    now = int(time.time() * 1000)

    if now - bars[-1][0] > minutes * 60 * 1000 * 3:
        return None

    closes = [price for _, price in bars]

    return {
        "close": closes[-1],
        "ema20": ema(closes, 20),
        "ema50": ema(closes, 50),
        "rsi": rsi(closes)
    }


def trend(data):
    if data is None:
        return "UNKNOWN"

    if data["close"] > data["ema20"] > data["ema50"]:
        return "BULLISH"

    if data["close"] < data["ema20"] < data["ema50"]:
        return "BEARISH"

    return "NEUTRAL"


def signal(m5, m15):
    if m5 is None or m15 is None:
        return "WAIT"

    if (
        trend(m5) == "BULLISH"
        and trend(m15) == "BULLISH"
        and 50 < m5["rsi"] < 70
    ):
        return "BUY"

    if (
        trend(m5) == "BEARISH"
        and trend(m15) == "BEARISH"
        and 30 < m5["rsi"] < 50
    ):
        return "SELL"

    return "WAIT"


print("XAUUSD BOT - DEMO READ ONLY", flush=True)
print("EMA + RSI ANALYSIS ENABLED", flush=True)

while True:
    try:
        headers, columns, params = connect()

        last_analysis = 0
        m5 = None
        m15 = None

        while True:
            state = api(
                f"/trade/accounts/{ACCOUNT_ID}/state",
                headers
            )["d"]["accountDetailsData"]

            if len(columns) != len(state):
                raise ValueError("Account data mismatch")

            details = {
                c["id"]: v
                for c, v in zip(columns, state)
            }

            query = urllib.parse.urlencode(params)

            quote = api(
                "/trade/quotes?" + query,
                headers
            )["d"]

            bid = float(quote["bp"])
            ask = float(quote["ap"])

            if bid <= 0 or ask < bid:
                raise ValueError("Invalid quote")

            spread = round(ask - bid, 3)

            print("--------------------", flush=True)
            print("UTC:", datetime.now(timezone.utc).isoformat(), flush=True)
            print("XAUUSD BID:", bid, flush=True)
            print("XAUUSD ASK:", ask, flush=True)
            print("SPREAD:", spread, flush=True)
            print("BALANCE:", details.get("balance"), "USD", flush=True)
            print("POSITIONS:", details.get("positionsCount"), flush=True)
            print("OPEN PNL:", details.get("openNetPnL"), flush=True)
            print("TODAY PNL:", details.get("todayNet"), flush=True)

            if time.time() - last_analysis >= 60:
                bars5 = get_candles(headers, params, 5)
                bars15 = get_candles(headers, params, 15)

                print("M5 CANDLES:", len(bars5), flush=True)
                print("M15 CANDLES:", len(bars15), flush=True)

                m5 = analyze(bars5, 5)
                m15 = analyze(bars15, 15)

                print("M5 TREND:", trend(m5), flush=True)
                print("M15 TREND:", trend(m15), flush=True)

                for name, data in [("M5", m5), ("M15", m15)]:
                    if data is not None:
                        print(name, "EMA20:", round(data["ema20"], 2), flush=True)
                        print(name, "EMA50:", round(data["ema50"], 2), flush=True)
                        print(name, "RSI:", round(data["rsi"], 2), flush=True)

                print("TEST SIGNAL:", signal(m5, m15), flush=True)

                last_analysis = time.time()

            print("MODE: READ ONLY - NO ORDERS", flush=True)

            time.sleep(INTERVAL)

    except urllib.error.HTTPError as error:
        print("HTTP ERROR:", error.code, flush=True)
        print("Retrying in 60 seconds", flush=True)
        time.sleep(60)

    except Exception as error:
        print("ERROR:", type(error).__name__, flush=True)
        print("Retrying in 60 seconds", flush=True)
        time.sleep(60)
