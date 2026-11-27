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

    query = urllib.parse.urlencode({
        "routeId": route["id"],
        "tradableInstrumentId": gold["tradableInstrumentId"]
    })

    print("LOGIN SUCCESSFUL", flush=True)
    print("CORRECT ACCOUNT FOUND", flush=True)
    print("XAUUSD FOUND", flush=True)

    return headers, columns, query

print("XAUUSD BOT - DEMO READ ONLY", flush=True)
print("MONITORING EVERY 30 SECONDS", flush=True)

while True:
    try:
        headers, columns, query = connect()

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
            print("MODE: READ ONLY", flush=True)

            time.sleep(INTERVAL)

    except urllib.error.HTTPError as error:
        print("HTTP ERROR:", error.code, flush=True)
        print("Retrying in 60 seconds", flush=True)
        time.sleep(60)

    except Exception as error:
        print("ERROR:", type(error).__name__, flush=True)
        print("Retrying in 60 seconds", flush=True)
        time.sleep(60)

