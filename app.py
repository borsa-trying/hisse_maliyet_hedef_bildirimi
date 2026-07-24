import os
import threading
import time
import random
import requests
from flask import Flask


# ================== ENV AYARLARI ==================

TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


# ================== FLASK ==================

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

    payload = {
        "chat_id": CHAT_ID,
        "text": metin,
        "parse_mode": "Markdown"
    }

    try:
        response = requests.post(
            url,
            data=payload,
            timeout=10
        )

        if response.status_code != 200:
            print("Telegram hata:", response.text)

    except Exception as hata:
        print("Telegram exception:", hata)


def telegram_hata(metin):
    if not TOKEN or not CHAT_ID:
        return

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"

    payload = {
        "chat_id": CHAT_ID,
        "text": metin
    }

    try:
        requests.post(
            url,
            data=payload,
            timeout=10
        )

    except Exception:
        pass


# ================== TRADINGVIEW ==================

def tum_fiyatlari_cek(semboller):
    url = "https://scanner.tradingview.com/turkey/scan"

    payload = {
        "symbols": {
            "tickers": [
                f"BIST:{sembol}"
                for sembol in semboller
            ],
            "query": {
                "types": []
            }
        },
        "columns": [
            "close"
        ]
    }

    try:
        response = requests.post(
            url,
            json=payload,
            timeout=10
        )

        # TradingView çok fazla istek hatası
        if response.status_code == 429:
            telegram_hata(
                "429 Too Many Requests alindi. "
                "120 saniye bekleniyor."
            )

            time.sleep(120)
            return {}

        if response.status_code != 200:
            telegram_hata(
                f"TradingView HTTP Hata: "
                f"{response.status_code}"
            )

            return {}

        data = response.json()

        if "data" not in data or not data["data"]:
            telegram_hata(
                "TradingView veri döndürmedi!"
            )

            return {}

        fiyatlar = {}
        gelen_semboller = []

        for item in data["data"]:
            sembol = item["s"].split(":")[1]
            fiyat = item["d"][0]

            fiyatlar[sembol] = fiyat
            gelen_semboller.append(sembol)

        # TradingView'da bulunamayan hisse isimleri
        eksik_semboller = (
            set(semboller) - set(gelen_semboller)
        )

        for eksik_sembol in eksik_semboller:
            telegram_hata(
                f"HATALI HISSE ADI: {eksik_sembol}"
            )

        return fiyatlar

    except Exception as hata:
        telegram_hata(
            f"TradingView Exception: {hata}"
        )

        return {}


# ================== HİSSE LİSTESİ ==================

takipler = [
    {
        "ad": "KOPOL",
        "maliyet": 6.01,
        "hedef": 6.48,
        "alt_limit": 5.73
    },
    {
        "ad": "EUREN",
        "maliyet": "almadim",
        "hedef": 6.90,
        "alt_limit": 5.05
    },
    {
        "ad": "ALTNY",
        "maliyet": 16.17,
        "hedef": 19.91,
        "alt_limit": 15.40
    },
    {
        "ad": "QUAGR",
        "maliyet": 2.71,
        "hedef": 2.75,
        "alt_limit": 2.61
    },
    {
        "ad": "CVKMD",
        "maliyet": 8.78,
        "hedef": 50.37,
        "alt_limit": 41.52
    },
    {
        "ad": "DOAS",
        "maliyet": 248.94,
        "hedef": 285.37,
        "alt_limit": 218.82
    },
    {
        "ad": "TURSG",
        "maliyet": 8.21,
        "hedef": 12.37,
        "alt_limit": 11.33
    },
    {
        "ad": "ISMEN",
        "maliyet": 39.25,
        "hedef": 54.30,
        "alt_limit": 44.09
    },
    {
        "ad": "PGSUS",
        "maliyet": 221.2,
        "hedef": 272.1,
        "alt_limit": 195.6
    },
    {
        "ad": "TTKOM",
        "maliyet": 44.5,
        "hedef": 72.1,
        "alt_limit": 62.89
    },
    {
        "ad": "TUPRS",
        "maliyet": 162.84,
        "hedef": 254.5,
        "alt_limit": 222.2
    },
    {
        "ad": "ALARK",
        "maliyet": 88.60,
        "hedef": 119.5,
        "alt_limit": 107.2
    },
    {
        "ad": "AKBNK",
        "maliyet": 52.90,
        "hedef": 112,
        "alt_limit": 81.2
    },
    {
        "ad": "AEFES",
        "maliyet": 19.76,
        "hedef": 22.18,
        "alt_limit": 18.63
    },
    {
        "ad": "ISCTR",
        "maliyet": 13.42,
        "hedef": 19.72,
        "alt_limit": 16.63
    },
    {
        "ad": "ASTOR",
        "maliyet": 95.24,
        "hedef": 193.0,
        "alt_limit": 151.0
    },
    {
        "ad": "THYAO",
        "maliyet": 273.3,
        "hedef": 340.0,
        "alt_limit": 307.0
    }
]


# ================== BİLDİRİM KİLİTLERİ ==================
#
# Fiyat hedefin üzerindeyken yalnızca bir mesaj gönderilir.
# Fiyat hedefin altına inerse hedef bildirimi yeniden açılır.
#
# Fiyat alt limitin altındayken yalnızca bir mesaj gönderilir.
# Fiyat alt limitin üzerine çıkarsa alt limit bildirimi yeniden açılır.
#
# Tarih kullanılmadığı için gece saat 03.00'te kilit sıfırlanmaz.

aktif_bildirimler = set()


# ================== BOT DÖNGÜSÜ ==================

def bot_loop():
    semboller = [
        hisse["ad"]
        for hisse in takipler
    ]

    telegram_mesaj(
        "🤖 Bot Render üzerinde başladı!"
    )

    print("Cloud-Ready Bot Başladı...")

    while True:
        fiyatlar = tum_fiyatlari_cek(semboller)

        for hisse in takipler:
            try:
                ad = hisse["ad"]
                fiyat = fiyatlar.get(ad)

                if fiyat is None:
                    continue

                hedef_anahtari = f"{ad}_hedef"
                alt_limit_anahtari = f"{ad}_alt"


                # ================== HEDEF KONTROLÜ ==================

                if fiyat >= hisse["hedef"]:

                    if (
                        hedef_anahtari
                        not in aktif_bildirimler
                    ):
                        mesaj = (
                            f"*HEDEF AŞILDI*\n\n"
                            f"Hisse: `{ad}`\n"
                            f"Güncel: {fiyat} TL\n"
                            f"Hedef: {hisse['hedef']} TL\n"
                            f"Maliyet: "
                            f"{hisse['maliyet']} TL"
                        )

                        telegram_mesaj(mesaj)

                        aktif_bildirimler.add(
                            hedef_anahtari
                        )

                else:
                    # Fiyat hedefin altına inince
                    # hedef bildirimi yeniden açılır.
                    aktif_bildirimler.discard(
                        hedef_anahtari
                    )


                # ================== ALT LİMİT KONTROLÜ ==================

                if fiyat <= hisse["alt_limit"]:

                    if (
                        alt_limit_anahtari
                        not in aktif_bildirimler
                    ):
                        mesaj = (
                            f"*ALT LİMİT KIRILDI*\n\n"
                            f"Hisse: `{ad}`\n"
                            f"Güncel: {fiyat} TL\n"
                            f"Alt Limit: "
                            f"{hisse['alt_limit']} TL\n"
                            f"Maliyet: "
                            f"{hisse['maliyet']} TL"
                        )

                        telegram_mesaj(mesaj)

                        aktif_bildirimler.add(
                            alt_limit_anahtari
                        )

                else:
                    # Fiyat alt limitin üzerine çıkınca
                    # alt limit bildirimi yeniden açılır.
                    aktif_bildirimler.discard(
                        alt_limit_anahtari
                    )

            except Exception as hata:
                hisse_adi = hisse.get(
                    "ad",
                    "Bilinmeyen"
                )

                telegram_hata(
                    f"Hisse Döngü Exception "
                    f"({hisse_adi}): {hata}"
                )


        # Her kontrolden sonra 45–65 saniye bekle
        bekleme = random.randint(45, 65)
        time.sleep(bekleme)


# ================== BOTU BAŞLAT ==================

threading.Thread(
    target=bot_loop,
    daemon=True
).start()


# ================== WEB SERVİSİNİ BAŞLAT ==================

if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(
            os.environ.get(
                "PORT",
                5000
            )
        )
    )
