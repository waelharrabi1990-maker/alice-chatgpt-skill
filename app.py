from flask import Flask, request, jsonify
import os, datetime, requests, json

app = Flask(__name__)

# ---------- Region (Doha, Qatar) ----------
LAT, LON = 25.2854, 51.5310
TIMEZONE = "auto"   # set TZ=Asia/Qatar on Render for correct local date

# ---------- Small utils ----------
def round_s(x, n=1):
    try:
        return str(round(float(x), n))
    except Exception:
        return "—"

def ttl_cache(seconds=600):
    """Tiny in-process TTL cache."""
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

def now_local():
    return datetime.datetime.now()  # respect TZ env on Render

# ---------- Data fetchers (no API keys) ----------
@ttl_cache(600)
def fetch_weather():
    """Air temp (°C), humidity (%), precip (mm/h), wind (m/s)."""
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LAT}&longitude={LON}"
        "&current=temperature_2m,relative_humidity_2m,precipitation,wind_speed_10m"
        f"&timezone={TIMEZONE}"
    )
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    cur = r.json().get("current", {})
    return {
        "t_air": cur.get("temperature_2m"),
        "humidity": cur.get("relative_humidity_2m"),
        "precip": cur.get("precipitation"),
        "wind": cur.get("wind_speed_10m"),
    }

@ttl_cache(600)
def fetch_sea_temp():
    url = (
        "https://marine-api.open-meteo.com/v1/marine"
        f"?latitude={LAT}&longitude={LON}"
        "&current=sea_surface_temperature"
        f"&timezone={TIMEZONE}"
    )
    r = requests.get(url, timeout=8)
    r.raise_for_status()
    return r.json().get("current", {}).get("sea_surface_temperature")

@ttl_cache(300)
def fetch_crypto():
    """BTC & XRP in USD."""
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
    """XAU→USD with solid fallback."""
    # Primary: XAU -> USD
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=XAU&to=USD", timeout=8)
        r.raise_for_status()
        res = r.json().get("result")
        if res:
            return float(res)  # USD per 1 XAU
    except Exception:
        pass
    # Fallback: USD -> XAU (invert)
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=USD&to=XAU", timeout=8)
        r.raise_for_status()
        rate = r.json().get("result")
        if rate and float(rate) != 0.0:
            return 1.0 / float(rate)
    except Exception:
        pass
    return None

# ---------- Quotes ----------
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

# ---------- Brief builder ----------
def build_morning_brief():
    dt = now_local()
    weekday = ["Понедельник","Вторник","Среда","Четверг","Пятница","Суббота","Воскресенье"][dt.weekday()]
    dstr = dt.strftime("%d.%m.%Y")

    # Weather
    try:
        w = fetch_weather()
        t_air = f"{round_s(w['t_air'],1)}°C" if w.get("t_air") is not None else "—"
        hum = f"{round_s(w.get('humidity'),0)}%"
        wind_ms = w.get("wind")
        wind = f"{round_s(float(wind_ms)*3.6,0)} км/ч" if wind_ms is not None else "—"
        rain = "да" if (w.get("precip") is not None and float(w["precip"]) > 0) else "нет"
    except Exception:
        t_air, hum, wind, rain = "—", "—", "—", "—"

    # Sea temp
    try:
        sea = fetch_sea_temp()
        t_water = f"{round_s(sea,1)}°C" if sea is not None else "—"
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

    quote = quote_of_the_day(dt)

    text = (
        f"{weekday}, {dstr}\n"
        f"Катар — Погода: воздух {t_air}, вода {t_water}, ветер {wind}, дождь: {rain}, влажность {hum}.\n"
        f"Цены: BTC {btc}, Золото {gold} за унцию, XRP {xrp}.\n"
        f"Цитата дня: {quote}\n"
        f"Сказать ещё раз или завершить?"
    )
    # Optional: shorter TTS line
    tts = (
        f"{weekday}, {dstr}. "
        f"Катар: воздух {t_air}, вода {t_water}, ветер {wind}. "
        f"BTC {btc}, золото {gold}, XRP {xrp}. "
        f"{quote}"
    )
    return text, tts

# ---------- Alice-safe responses ----------
def alice_ok(version, session, text, tts=None, buttons=None, end=False):
    return jsonify({
        "version": version or "1.0",
        "session": session or {"message_id": 0, "session_id": "", "user_id": ""},
        "response": {
            "text": (text or "—")[:1024],
            "tts": ((tts or text or "—"))[:1024],
            "end_session": bool(end),
            "buttons": buttons or []
        }
    })

# ---------- Routes ----------
@app.route("/", methods=["POST"])
def dialog():
    # Never crash/400 on Alice
    req = request.get_json(silent=True) or {}
    version = req.get("version", "1.0")
    session = req.get("session") or {"message_id": 0, "session_id": "", "user_id": ""}
    utter = (req.get("request", {}).get("original_utterance") or "").lower().strip()

    # (Optional) compact log for debugging in Render
    try:
        app.logger.info("Alice req: %s", json.dumps({
            "ver": version, "new": req.get("session", {}).get("new", False), "utt": utter
        }, ensure_ascii=False))
    except Exception:
        pass

    try:
        # First launch
        if req.get("session", {}).get("new"):
            text = "Добро пожаловать в Утреннее Шоу. Скажи: «Запусти выпуск»."
            return alice_ok(version, session, text)

        # Triggers
        if any(k in utter for k in ["запусти выпуск", "утренний выпуск", "дай сводку", "start", "выпуск"]):
            text, tts = build_morning_brief()
            return alice_ok(version, session, text, tts, buttons=[
                {"title": "Ещё раз", "hide": True},
                {"title": "Стоп", "hide": True},
            ])

        if "ещё" in utter:
            text, tts = build_morning_brief()
            return alice_ok(version, session, text, tts, buttons=[
                {"title": "Ещё раз", "hide": True},
                {"title": "Стоп", "hide": True},
            ])

        if any(k in utter for k in ["стоп", "хватит", "выход", "заверши"]):
            return alice_ok(version, session, "Окей, мощного дня!", end=True)

        # Fallback prompt
        return alice_ok(version, session, "Скажи: «Запусти выпуск» или «Ещё раз».",
                        buttons=[{"title": "Запусти выпуск", "hide": True}])

    except Exception as e:
        # Safety net: always answer 200 OK
        app.logger.exception("handler_error: %s", e)
        return alice_ok(version, session, "Короткая пауза на линии. Скажи: «Запусти выпуск» ещё раз.")

@app.route("/", methods=["GET"])
def health():
    return "ok", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)))
