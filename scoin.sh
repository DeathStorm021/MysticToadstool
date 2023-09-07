#!/bin/bash

host="https://www.universal-cdn.com"
hanime_email=${EMAIL:-"$1"}
hanime_password=${PASSWORD:-"$2"}


getSHA256() {
    to_hash="$1"
    echo -n "$to_hash" | sha256sum | awk '{print $1}'
}

getXHeaders() {
    XClaim=$(date +%s)
    XSig=$(getSHA256 "9944822${XClaim}8${XClaim}113")
    echo "X-Signature-Version: app2"
    echo "X-Claim: $XClaim"
    echo "X-Signature: $XSig"
}

login() {
    email="$1"
    password="$2"
    s=$(curl -s -X POST -H "Content-Type: application/json;charset=utf-8" -H "$(getXHeaders)" -d "{\"burger\":\"$email\",\"fries\":\"$password\"}" "$host/rapi/v4/sessions")

    if echo "$s" | grep -q '{"errors":["Unauthorized"]}' ; then
        echo "[!!!] Login failed, please check your credentials."
        exit 1
    fi

    getInfo "$s"
}

getInfo() {
    response="$1"
    session_token=$(echo "$response" | jq -r '.session_token')
    uid=$(echo "$response" | jq -r '.user.id')
    name=$(echo "$response" | jq -r '.user.name')
    coins=$(echo "$response" | jq -r '.user.coins')
    last_clicked=$(echo "$response" | jq -r '.user.last_rewarded_ad_clicked_at')
    available_keys=$(echo "$response" | jq -r '.env.mobile_apps | keys[]')
    version=""

    if [[ "$available_keys" == *"_build_number"* ]] ; then
        version=$(echo "$response" | jq -r '.env.mobile_apps._build_number')
    elif [[ "$available_keys" == *"osts_build_number"* ]] ; then
        version=$(echo "$response" | jq -r '.env.mobile_apps.osts_build_number')
    elif [[ "$available_keys" == *"severilous_build_number"* ]] ; then
        version=$(echo "$response" | jq -r '.env.mobile_apps.severilous_build_number')
    else
        echo "[!!!] Unable to find the build number for the latest mobile app, please report an issue on github."
        exit 1
    fi

    echo "session_token=$session_token"
    echo "uid=$uid"
    echo "name=$name"
    echo "coins=$coins"
    echo "last_clicked=$last_clicked"
    echo "version=$version"
}

getCoins() {
    version="$1"
    uid="$2"
    s=$(curl -s -X POST -H "$(getXHeaders)" "$host/rapi/v4/coins" -d "reward_token=$(getSHA256 "coins$version|$uid|$(date +%s)|coins$version")|$(date +%s)&version=$version")

    if echo "$s" | grep -q '{"errors":["Unauthorized"]}' ; then
        echo "[!!!] Something went wrong, please report issue on github."
        exit 1
    fi

    rewarded_amount=$(echo "$s" | jq -r '.rewarded_amount')
    echo "You received $rewarded_amount coins."
}

main() {
    info=$(login "$hanime_email" "$hanime_password")

    session_token=$(echo "$info" | grep "session_token=" | cut -d'=' -f2)
    s=$(curl -s -H "X-Session-Token: $session_token" "$host")

    echo "[*] Logged in as $(echo "$info" | grep "name=" | cut -d'=' -f2)"
    echo "[*] Coins count: $(echo "$info" | grep "coins=" | cut -d'=' -f2)"

    last_clicked=$(echo "$info" | grep "last_clicked=" | cut -d'=' -f2)
    if [ -n "$last_clicked" ]; then
        echo "[*] Last clicked on $(date -d @$last_clicked '+%c') UTC"
        previous_time=$last_clicked
        current_time=$(date +%s)
        if [ $((current_time - previous_time)) -lt $((3 * 3600)) ]; then
            echo "[!!!] You've already clicked on an ad less than 3 hrs ago."
            exit 1
        fi
    else
        echo "[*] Never clicked on an ad"
    fi

    getCoins "$(echo "$info" | grep "version=" | cut -d'=' -f2)" "$(echo "$info" | grep "uid=" | cut -d'=' -f2)"
}

main
