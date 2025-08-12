from flask import Flask, request, jsonify
import os, datetime, requests

app = Flask(__name__)

# ---- Location (Doha, Qatar)
LAT, LON = 25.2854, 51.5310
TIMEZONE = "auto"  # server TZ must be set to Asia/Qatar on Render

# ---- Helpers
def alice_response(req, text, tts=None, end=False, buttons=None):
    return jsonify({
        "version": req.get("version", "1.0"),
        "session": req["session"],
        "response": {
            "text": text[:1024],
            "tts": (tts or text)[:1024],
            "end_session": end,
            "buttons": buttons or []
        }
    })

def round_s(x, n=1):
    try:
        return str(round(float(x), n))
    except Exception:
        return "—"

def ttl_cache(seconds=600):
    """Tiny TTL cache (in-proc)"""
    def decorator(fn):
        cache = {}
        def wrapper(*args, **kwargs):
            key = (fn.__name__, args, tuple(sorted(kwargs.items())))
            now = datetime.datetime.utcnow().timestamp()
            if key in cache:
                ts, val = cache[key]
                if now - ts < seconds:
                    return val
            val = fn(*args, **kwargs)
            cache[key] = (now, val)
            return val
        return wrapper
    return decorator

def today_local():
    # Render env var TZ=Asia/Qatar recommended
    return datetime.datetime.now()

# ---- Data fetchers
@ttl_cache(600)
def fetch_weather():
    """Air temp, humidity, precip, wind (m/s)"""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        f"&timezone={TIMEZONE}"
    )
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    j = r.json().get("current", {})
    return {
        "t_air": j.get("temperature_2m"),
        "humidity": j.get("relative_humidity_2m"),
        "precip": j.get("precipitation"),
        "wind": j.get("wind_speed_10m"),
    }

@ttl_cache(600)
def fetch_sea_temp():
    """Sea surface temperature"""
    url = (
        "https://marine-api.open-meteo.com/v1/marine"
        f"?latitude={LAT}&longitude={LON}"
        "&current=sea_surface_temperature"
        f"&timezone={TIMEZONE}"
    )
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    j = r.json().get("current", {})
    return j.get("sea_surface_temperature")

@ttl_cache(300)
def fetch_crypto():
    """BTC & XRP in USD via CoinGecko (no API key)"""
    url = ("https://api.coingecko.com/api/v3/simple/price"
           "?ids=bitcoin,ripple&vs_currencies=usd")
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    j = r.json()
    return {
        "btc_usd": j.get("bitcoin", {}).get("usd"),
        "xrp_usd": j.get("ripple", {}).get("usd"),
    }

@ttl_cache(600)
def fetch_gold():
    """XAU→USD with robust fallback (no API key)"""
    # Primary: XAU -> USD
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=XAU&to=USD", timeout=8)
        r.raise_for_status()
        j = r.json()
        res = j.get("result")
        if res:
            return float(res)  # USD per 1 XAU
    except Exception:
        pass
    # Fallback: USD -> XAU, then invert
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

# ---- Quotes
QUOTES = [
    "Дисциплина бьёт мотивацию в любой день недели.",
    "Маленькие шаги ежедневно дают большие рывки раз в квартал.",
    "Фокус — это умение сказать «нет» девяноста идеям из ста.",
    "Сила в том, чтобы делать правильно, когда никто не смотрит.",
    "Качество жизни — это качество твоих решений.",
    "Результаты — это математика, эмоции — побочный шум.",
    "Планируй как стратег, действуй как инженер, фиксируй как трейдер.",
    "Ты не обязан быть идеальным — ты обязан быть последовательным.",
    "Сомнения уходят после первых 30 минут работы.",
    "Скорость без вектора — просто суета.",
]
def quote_of_the_day(dt: datetime.datetime):
    return QUOTES[dt.toordinal() % len(QUOTES)]

# ---- Brief builder
def build_morning_brief():
    now = today_local()
    weekday_ru = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"][now.weekday()]
    date_str = now.strftime("%d.%m.%Y")

    # Weather
    try:
        w = fetch_weather()
        t_air = f"{round_s(w.get('t_air'),1)}°C"
        humidity = f"{round_s(w.get('humidity'),0)}%"
        wind_ms = w.get("wind")
        precip = w.get("precip")
        wind_kmh = None if wind_ms is None else float(wind_ms) * 3.6
        wind = f"{round_s(wind_kmh,0)} км/ч" if wind_kmh is not None else "—"
        rain = "да" if (precip is not None and float(precip) > 0) else "нет"
    except Exception:
        t_air, humidity, wind, rain = "—", "—", "—", "—"

    # Sea temp
    try:
        t_sea = fetch_sea_temp()
        t_water = f"{round_s(t_sea,1)}°C" if t_sea is not None else "—"
    except Exception:
        t_water = "—"

    # Prices
    try:
        c = fetch_crypto()
        btc = f"${round_s(c.get('btc_usd'),0)}" if c.get('btc_usd') else "—"
        xrp = f"${round_s(c.get('xrp_usd'),3)}" if c.get('xrp_usd') else "—"
    except Exception:
        btc, xrp = "—", "—"

    try:
        xau = fetch_gold()
        gold = f"${round_s(xau,2)}" if xau is not None else "—"
    except Exception:
        gold = "—"

    q = quote_of_the_day(now)

    text = (
        f"{weekday_ru}, {date_str}\n"
        f"Катар — Погода: воздух {t_air}, вода {t_water}, ветер {wind}, дождь: {rain}, влажность {humidity}.\n"
        f"Цены: BTC {btc}, Золото {gold} за унцию, XRP {xrp}.\n"
        f"Цитата дня: {q}\n"
        f"Сказать ещё раз или завершить?"
    )
    return text

# ---- Routes
@app.route("/", methods=["POST"])
def dialog():
    req = request.get_json(force=True)

    # First launch greeting
    if req["session"]["new"]:
        return alice_response(req, "Добро пожаловать в Утреннее Шоу. Скажи: «Запусти выпуск».")
    
    utter = (req["request"].get("original_utterance") or "").lower().strip()

    # Triggers (ASCII 'start' included to bypass Cyrillic issues in tests)
    if any(k in utter for k in ["запусти выпуск", "утренний выпуск", "дай сводку", "start", "выпуск"]):
        text = build_morning_brief()
        return alice_response(req, text, buttons=[{"title":"Ещё раз","hide":True}, {"title":"Стоп","hide":True}])

    if "ещё" in utter:
        text = build_morning_brief()
        return alice_response(req, text, buttons=[{"title":"Ещё раз","hide":True}, {"title":"Стоп","hide":True}])

    if any(k in utter for k in ["стоп","хватит","выход","заверши"]):
        return alice_response(req, "Окей, мощного дня!", end=True)

    return alice_response(req, "Скажи: «Запусти выпуск» или «Ещё раз».", buttons=[{"title":"Запусти выпуск","hide":True}])

@app.route("/", methods=["GET"])
def health():
    return "ok", 200

if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
