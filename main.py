
import os
import json
import time
import urllib.request
import urllib.error
import urllib.parse

BASE = "https://demo.tradelocker.com/backend-api"
ACCOUNT_ID = "2656810"

def api(path, headers=None, data=None):
    request = urllib.request.Request(
        BASE + path,
        headers=headers or {},
        data=data,
        method="POST" if data is not None else "GET"
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)

print("XAUUSD BOT - DEMO READ ONLY", flush=True)

try:
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

    print("LOGIN SUCCESSFUL", flush=True)

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

    print("CORRECT ACCOUNT FOUND", flush=True)
    print("Currency:", account["currency"], flush=True)

    config = api("/trade/config", headers)["d"]

    columns = config["accountDetailsConfig"]["columns"]

    state = api(
        f"/trade/accounts/{ACCOUNT_ID}/state",
        headers
    )["d"]["accountDetailsData"]

    if len(columns) != len(state):
        raise ValueError("Account data mismatch")

    print("ACCOUNT DETAILS:", flush=True)

    for column, value in zip(columns, state):
        print(column["id"], ":", value, flush=True)

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

    quote = api(
        "/trade/quotes?" + query,
        headers
    )["d"]

    print("XAUUSD FOUND", flush=True)
    print("BID:", quote["bp"], flush=True)
    print("ASK:", quote["ap"], flush=True)

    print("READ ONLY TEST COMPLETE", flush=True)

except urllib.error.HTTPError as error:
    print("HTTP ERROR:", error.code, flush=True)

except KeyError as error:
    print("Missing field:", error, flush=True)

except Exception as error:
    print("TEST FAILED:", type(error).__name__, flush=True)

while True:
    time.sleep(60)
