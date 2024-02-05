import os
import time
import json
import sys
from hashlib import sha256
from datetime import datetime, timedelta

import requests
from dateutil import parser

host = "https://www.universal-cdn.com"


def getSHA256(to_hash):
    """Get SHA256 hash."""
    m = sha256()
    m.update(to_hash.encode())
    return m.hexdigest()

def getXHeaders():
    XClaim = str(int(time.time()))
    XSig = getSHA256(f"9944822{XClaim}8{XClaim}113")
    headers = {"X-Signature-Version": "app2", "X-Claim": XClaim, "X-Signature": XSig}
    return headers

def login(s: requests.Session, email, password):
    """Login into your account."""
    s.headers.update(getXHeaders())
    response = s.post(f"{host}/rapi/v4/sessions",
                      headers={"Content-Type": "application/json;charset=utf-8"},
                      data=f'{{"burger":"{email}","fries":"{password}"}}')

    if '{"errors":["Unauthorized"]}' in response.text:
        raise SystemExit(f"[!!!] Login failed for {email}, please check your credentials.")

    return getInfo(response.text)

def getInfo(response):
    """Parse out only relevant info."""
    received = json.loads(response)

    ret = {
        "session_token": received["session_token"],
        "uid": received["user"]["id"],
        "name": received["user"]["name"],
        "coins": received["user"]["coins"],
        "last_clicked": received["user"]["last_rewarded_ad_clicked_at"]
    }

    available_keys = list(received["env"]["mobile_apps"].keys())

    if "_build_number" in available_keys:
        ret["version"] = received["env"]["mobile_apps"]["_build_number"]
    elif "osts_build_number" in available_keys:
        ret["version"] = received["env"]["mobile_apps"]["osts_build_number"]
    elif "severilous_build_number" in available_keys:
        ret["version"] = received["env"]["mobile_apps"]["severilous_build_number"]
    else:
        raise SystemExit("[!!!] Unable to find the build number for the latest mobile app, please report an issue on GitHub.")

    return ret

def getCoins(s: requests.Session, version, uid):
    
    s.headers.update(getXHeaders())

    curr_time = str(int(time.time()))
    to_hash = f"coins{version}|{uid}|{curr_time}|coins{version}"

    data = {"reward_token": getSHA256(to_hash) + f"|{curr_time}", "version": f"{version}"}

    response = s.post(f"{host}/rapi/v4/coins", data=data)

    if '{"errors":["Unauthorized"]}' in response.text:
        raise SystemExit("[!!!] Something went wrong, please report the issue on GitHub")
    print(f"You received {json.loads(response.text)['rewarded_amount']} coins.")

def send_to_discord_webhook(info):
    webhook_url = os.environ.get('WEBHOOK')

    # Prepare the data to be sent to the Discord webhook
    data = {
        "content": f"Coins Info:\nName: {info['name']}\nCoins: {info['coins']}"
    }

    # Send the data to the Discord webhook
    response = requests.post(webhook_url, json=data)

def main():
    s = requests.Session()

    # Get the list of emails and passwords from GitHub secrets
    emails = os.environ.get('EMAILS', '').split(',')
    passwords = os.environ.get('PASSWORD', '').split(',')

    # Ensure the number of emails matches the number of passwords
    if len(emails) != len(passwords):
        raise ValueError("Number of emails does not match number of passwords")

    for email, password in zip(emails, passwords):
        info = login(s, email, password)

        s.headers.update({"X-Session-Token": info["session_token"]})

        print(f"[*] Logged in as {info['name']} ")
        print(f"[*] Coins count: {info['coins']}")
        print(f"[*] Version: {info['version']}") 

        if info['last_clicked'] is not None:
            print(f"[*] Last clicked on {parser.parse(info['last_clicked']).ctime()} UTC")

            previous_time = parser.parse(info["last_clicked"]).timestamp()
            if time.time() - previous_time < 3 * 3600:
                print("[*] You've already clicked on an ad less than 3 hours ago.")
                continue  # Skip to the next email

        else:
            print(f"[*] Never clicked on an ad")
        current_day = datetime.utcnow().weekday()  # 0 is Monday, 1 is Tuesday, and so on
        current_time = datetime.utcnow().time()

        if current_day == 0 and current_time >= datetime.strptime("01:00", "%H:%M").time() and current_time <= datetime.strptime("04:00", "%H:%M").time():
        # Send the list of info['name'] and info['coins'] to Discord webhook
            send_to_discord_webhook(info)
        getCoins(s, info["version"], info["uid"])


if __name__ == "__main__":
    main()
