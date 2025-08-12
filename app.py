from flask import Flask, request, jsonify
import requests
from datetime import datetime
from functools import lru_cache

app = Flask(__name__)

# Cached fetch to avoid hitting API too often
def ttl_cache(seconds=600):
    def wrapper(func):
        cache = {}
        def inner(*args, **kwargs):
            now = datetime.now().timestamp()
            if args in cache:
                result, timestamp = cache[args]
                if now - timestamp < seconds:
                    return result
            result = func(*args, **kwargs)
            cache[args] = (result, now)
            return result
        return inner
    return wrapper


@ttl_cache(600)
def fetch_weather():
    try:
        url = "https://api.open-meteo.com/v1/forecast?latitude=25.2854&longitude=51.5310&current_weather=true"
        r = requests.get(url, timeout=8)
        r.raise_for_status()
        data = r.json()
        return data.get("current_weather", {})
    except Exception:
        return {}


@ttl_cache(600)
def fetch_btc():
    try:
        r = requests.get("https://api.coindesk.com/v1/bpi/currentprice/BTC.json", timeout=8)
        r.raise_for_status()
        data = r.json()
        return data["bpi"]["USD"]["rate_float"]
    except Exception:
        return None


@ttl_cache(600)
def fetch_xrp():
    try:
        r = requests.get("https://api.coingecko.com/api/v3/simple/price?ids=ripple&vs_currencies=usd", timeout=8)
        r.raise_for_status()
        data = r.json()
        return data["ripple"]["usd"]
    except Exception:
        return None


@ttl_cache(600)
def fetch_gold():
    # Primary: XAU -> USD
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=XAU&to=USD", timeout=8)
        r.raise_for_status()
        j = r.json()
        if j.get("result"):
            return j["result"]
    except Exception:
        pass
    # Fallback: USD -> XAU (invert)
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=USD&to=XAU", timeout=8)
        r.raise_for_status()
        j = r.json()
        rate = j.get("result")
        if rate and float(rate) != 0:
            return 1.0 / float(rate)
    except Exception:
        pass
    return None


def get_briefing():
    weather = fetch_weather()
    btc = fetch_btc()
    gold = fetch_gold()
    xrp = fetch_xrp()

    date_str = datetime.now().strftime("%A, %d.%m.%Y")
    weather_text = f"Катар — Погода: воздух {weather.get('temperature', '—')}°C, ветер {weather.get('windspeed', '—')} км/ч."
    prices_text = f"Цены: BTC ${btc if btc else '—'}, Золото ${round(gold, 2) if gold else '—'} за унцию, XRP ${xrp if xrp else '—'}."
    quote = "Цитата дня: Результаты – это математика, эмоции – побочный шум."

    return f"{date_str}\n{weather_text}\n{prices_text}\n{quote}\nСказать ещё раз или завершить?"


@app.route('/', methods=['POST'])
def alice_webhook():
    data = request.json
    user_command = data.get("request", {}).get("command", "").lower()

    if "start" in user_command or "выпуск" in user_command:
        text = get_briefing()
    else:
        text = "Скажи: «Запусти выпуск» или «Ещё раз»."

    return jsonify({
        "response": {
            "text": text,
            "tts": text,
            "buttons": [],
            "end_session": False
        },
        "session": data["session"],
        "version": data["version"]
    })


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)


