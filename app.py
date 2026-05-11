import os
import threading
import time
import random
import requests
from flask import Flask

# ================== ENV ==================
TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

app = Flask(__name__)

@app.route("/")
def home():
    return "BOT CALISIYOR", 200


# ================== TELEGRAM ==================
def telegram_mesaj(metin):
    if not TOKEN or not CHAT_ID:
        print("ENV eksik: BOT_TOKEN veya CHAT_ID yok!")
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": metin, "parse_mode": "Markdown"}

    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code != 200:
            print("Telegram hata:", r.text)
    except Exception as e:
        print("Telegram exception:", e)


def telegram_hata(metin):
    # Hatalar için sade metin (Markdown kapalı)
    if not TOKEN or not CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": metin}

    try:
        requests.post(url, data=payload, timeout=10)
    except:
        pass


# ================== TRADINGVIEW ==================
def tum_fiyatlari_cek(semboller):
    url = "https://scanner.tradingview.com/turkey/scan"
    payload = {
        "symbols": {
            "tickers": [f"BIST:{s}" for s in semboller],
            "query": {"types": []}
        },
        "columns": ["close"]
    }

    try:
        r = requests.post(url, json=payload, timeout=10)

        # ---- 429 YÖNETİMİ ----
        if r.status_code == 429:
            telegram_hata(" 429 Too Many Requests alindi. 120 saniye bekleniyor.")
            time.sleep(120)
            return {}

        if r.status_code != 200:
            telegram_hata(f" TradingView HTTP Hata: {r.status_code}")
            return {}

        data = r.json()

        if "data" not in data or not data["data"]:
            telegram_hata(" TradingView veri döndürmedi!")
            return {}

        fiyatlar = {}
        gelenler = []

        for item in data["data"]:
            symbol = item["s"].split(":")[1]
            fiyatlar[symbol] = item["d"][0]
            gelenler.append(symbol)

        # ---- HATALI HİSSE ADI ----
        eksikler = set(semboller) - set(gelenler)
        for e in eksikler:
            telegram_hata(f" HATALI HISSE ADI: {e}")

        return fiyatlar

    except Exception as e:
        telegram_hata(f" TradingView Exception: {e}")
        return {}


# ================== HİSSE LİSTESİ ==================
takipler = [
   # yatırım tavsiyesi degildir koda örnek amaçlıdır 
    {"ad": "ASTOR", "maliyet": 5.24, "hedef": 20000.0, "alt_limit": 151.0},
    {"ad": "THYAO", "maliyet": 23.3, "hedef": 20000.0, "alt_limit": 307.0},
]

# ================== SPAM ENGEL + TEKRAR TETİKLEME ==================
# Senin eski davranış:
# - hedef üstünde kaldıkça TEK mesaj
# - hedef altına inince kilit açılır
# - tekrar hedef üstüne çıkınca tekrar mesaj
ustte_kilit = set()
altta_kilit = set()


def bot_loop():
    semboller = [h["ad"] for h in takipler]

    telegram_mesaj("🤖 Bot Render üzerinde başladı!")
    print("Cloud-Ready Bot Basladi...")

    while True:
        fiyatlar = tum_fiyatlari_cek(semboller)

        for hisse in takipler:
            try:
                ad = hisse["ad"]
                fiyat = fiyatlar.get(ad)

                if fiyat is None:
                    continue

                key_hedef = f"{ad}_hedef"
                key_alt = f"{ad}_alt"

                # ------- HEDEF -------
                if fiyat >= hisse["hedef"]:
                    # hedefi geçti -> daha önce kilitlenmediyse mesaj at
                    if key_hedef not in ustte_kilit:
                        mesaj = (
                            f"*HEDEF AŞILDI*\n\n"
                            f"Hisse: `{ad}`\n"
                            f"Güncel: {fiyat} TL\n"
                            f"Hedef: {hisse['hedef']} TL\n"
                            f"Maliyet: {hisse['maliyet']} TL"
                        )
                        telegram_mesaj(mesaj)
                        ustte_kilit.add(key_hedef)

                    # hedefin üstündeyken alt kilidi temizle
                    altta_kilit.discard(key_alt)

                else:
                    # hedef altına indi -> hedef kilidini kaldır (tekrar geçerse tekrar mesaj)
                    ustte_kilit.discard(key_hedef)

                # ------- ALT LIMIT -------
                if fiyat <= hisse["alt_limit"]:
                    if key_alt not in altta_kilit:
                        mesaj = (
                            f"*ALT LİMİT KIRILDI*\n\n"
                            f"Hisse: `{ad}`\n"
                            f"Güncel: {fiyat} TL\n"
                            f"Alt Limit: {hisse['alt_limit']} TL\n"
                            f"Maliyet: {hisse['maliyet']} TL"
                        )
                        telegram_mesaj(mesaj)
                        altta_kilit.add(key_alt)

                    # altın altındayken hedef kilidi temizle
                    ustte_kilit.discard(key_hedef)

                else:
                    # alt limit üstüne çıktı -> alt kilidini kaldır
                    altta_kilit.discard(key_alt)

            except Exception as e:
                telegram_hata(f" Hisse Döngü Exception ({hisse.get('ad')}): {e}")

        bekleme = random.randint(45, 65)
        time.sleep(bekleme)


threading.Thread(target=bot_loop, daemon=True).start()
