import os
import json
import time
import urllib.request
import urllib.error

BASE = "https://demo.tradelocker.com/backend-api"

print("TradeLocker TEST - READ ONLY", flush=True)

try:
    if os.environ["TL_ENVIRONMENT"].lower() != "demo":
        raise ValueError("Only DEMO allowed")

    credentials = {
        "email": os.environ["TL_EMAIL"],
        "password": os.environ["TL_PASSWORD"],
        "server": os.environ["TL_SERVER"]
    }

    request = urllib.request.Request(
        BASE + "/auth/jwt/token",
        data=json.dumps(credentials).encode(),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        token = json.load(response)["accessToken"]

    print("LOGIN SUCCESSFUL", flush=True)

    request = urllib.request.Request(
        BASE + "/auth/jwt/all-accounts",
        headers={"Authorization": "Bearer " + token}
    )

    with urllib.request.urlopen(request, timeout=30) as response:
        accounts = json.load(response)["accounts"]

    print("Accounts found:", len(accounts), flush=True)

    for account in accounts:
        print(
            "Account ID:", account.get("id"),
            "Balance:", account.get("aaccountBalance", "N/A"),
            "Currency:", account.get("currency"),
            flush=True
        )

    print("Connection test complete", flush=True)

except urllib.error.HTTPError as error:
    print("HTTP ERROR:", error.code, flush=True)

except KeyError:
    print("Missing variable or API field", flush=True)

except Exception as error:
    print("TEST FAILED:", type(error).__name__, flush=True)

while True:
    time.sleep(60)
