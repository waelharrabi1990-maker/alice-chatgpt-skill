HEADERS = {"User-Agent": "morning-show-skill/1.0 (+render)"}

@ttl_cache(60)
def fetch_crypto():
    """Return {'btc_usd': float|None, 'xrp_usd': float|None} with robust fallbacks."""
    btc = xrp = None

    # 1) Binance spot (very reliable, no key)
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT",
                         timeout=6, headers=HEADERS)
        r.raise_for_status()
        btc = float(r.json()["price"])
    except Exception:
        pass
    try:
        r = requests.get("https://api.binance.com/api/v3/ticker/price?symbol=XRPUSDT",
                         timeout=6, headers=HEADERS)
        r.raise_for_status()
        xrp = float(r.json()["price"])
    except Exception:
        pass

    # 2) Fallback: CoinGecko simple/price
    if btc is None or xrp is None:
        try:
            r = requests.get(
                "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ripple&vs_currencies=usd",
                timeout=6, headers=HEADERS
            )
            r.raise_for_status()
            j = r.json()
            btc = btc if btc is not None else float(j.get("bitcoin", {}).get("usd") or 0) or None
            xrp = xrp if xrp is not None else float(j.get("ripple", {}).get("usd") or 0) or None
        except Exception:
            pass

    return {"btc_usd": btc, "xrp_usd": xrp}


@ttl_cache(300)
def fetch_gold():
    """USD per 1 XAU (troy ounce) with multiple fallbacks + headers."""
    # 1) Metals.live spot feed
    try:
        r = requests.get("https://api.metals.live/v1/spot", timeout=6, headers=HEADERS)
        r.raise_for_status()
        arr = r.json()
        if isinstance(arr, list):
            for item in arr:
                if isinstance(item, dict) and "gold" in item:
                    val = float(item["gold"])
                    if val > 0:
                        return val
    except Exception:
        pass

    # 2) exchangerate.host XAU->USD
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=XAU&to=USD",
                         timeout=6, headers=HEADERS)
        r.raise_for_status()
        res = r.json().get("result")
        if res:
            return float(res)
    except Exception:
        pass

    # 3) exchangerate.host USD->XAU invert
    try:
        r = requests.get("https://api.exchangerate.host/convert?from=USD&to=XAU",
                         timeout=6, headers=HEADERS)
        r.raise_for_status()
        rate = r.json().get("result")
        if rate and float(rate) != 0.0:
            return 1.0 / float(rate)
    except Exception:
        pass

    return None
