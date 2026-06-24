"""
GTA 6 Collector's Edition Monitor — Headless-Version für Cron/CI.

Führt EINEN Durchlauf über alle Shop-URLs aus und postet bei einem Treffer
(Collector's-Edition-Erwähnung in der Nähe eines Verfügbarkeits-Hinweises)
einen Discord-Webhook und optional eine E-Mail. Keine GUI, keine
Endlosschleife — die Wiederholung übernimmt der Scheduler von außen
(z. B. der Cron-Trigger in .github/workflows/gta6-monitor.yml).

Konfiguration ausschließlich über Umgebungsvariablen, damit keine
Zugangsdaten im Code oder Repo landen:
  DISCORD_WEBHOOK_URL   - Pflicht für Discord-Alarme
  SMTP_USER, SMTP_PASS, ALERT_EMAIL  - optional, für zusätzlichen E-Mail-Alarm
  CE_KEYWORDS           - optional, Komma-getrennt, überschreibt die Defaults
  CONTEXT_WINDOW        - optional, Zeichen-Fenster um einen CE-Treffer (Default 300)
"""

import os
import requests
from bs4 import BeautifulSoup

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()

SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASS = os.environ.get("SMTP_PASS", "").strip()
ALERT_EMAIL = os.environ.get("ALERT_EMAIL", "").strip()

CE_KEYWORDS = [
    t.strip().lower()
    for t in os.environ.get(
        "CE_KEYWORDS",
        "collector's edition,collectors edition,collector edition,sammleredition,sammler-edition"
    ).split(",")
    if t.strip()
]
CONTEXT_WINDOW = int(os.environ.get("CONTEXT_WINDOW", "300"))

URLS = {
    "Amazon": "https://www.amazon.de/s?k=Grand+Theft+Auto+VI",
    "MediaMarkt": "https://www.mediamarkt.de/de/search.html?query=Grand+Theft+Auto+VI",
    "Saturn": "https://www.saturn.de/de/search.html?query=Grand+Theft+Auto+VI",
    "Rockstar": "https://store.rockstargames.com/de/",
}

KEYWORDS_IN_STOCK = ["vorbestellbar", "in den warenkorb", "pre-order", "add to cart", "lieferung", "verfügbar", "jetzt kaufen", "sofort lieferbar"]
KEYWORDS_SOLD_OUT = ["ausverkauft", "nicht verfügbar", "coming soon", "nicht lieferbar"]


def send_discord_alert(site, url, matched_term):
    if not DISCORD_WEBHOOK_URL:
        print(f"[WARN] Treffer bei {site}, aber kein DISCORD_WEBHOOK_URL gesetzt.")
        return
    message = (
        f"🚨 **GTA 6 COLLECTOR'S EDITION VERFÜGBAR!**\n"
        f"**Shop:** {site}\n**Treffer:** \"{matched_term}\"\n**Link:** {url}"
    )
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": message}, timeout=10)
        print(f"[OK] Discord-Alarm gesendet ({site}).")
    except Exception as e:
        print(f"[ERROR] Discord-Webhook fehlgeschlagen: {e}")


def send_email_alert(site, url, matched_term):
    if not (SMTP_USER and SMTP_PASS and ALERT_EMAIL):
        return
    import smtplib
    from email.mime.text import MIMEText

    body = f"GTA 6 Collector's Edition verfügbar bei {site}\nTreffer: {matched_term}\nLink: {url}"
    msg = MIMEText(body)
    msg["Subject"] = f"GTA 6 CE Alarm: {site}"
    msg["From"] = SMTP_USER
    msg["To"] = ALERT_EMAIL
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, ALERT_EMAIL, msg.as_string())
        server.quit()
        print(f"[OK] E-Mail-Alarm gesendet ({site}).")
    except Exception as e:
        print(f"[ERROR] E-Mail fehlgeschlagen: {e}")


def check_site(site, url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
        r = requests.get(url, headers=headers, timeout=15)
        text = BeautifulSoup(r.text, "html.parser").get_text(separator=" ").lower()
    except Exception as e:
        print(f"[ERROR] Verbindungsfehler {site}: {e}")
        return

    found_any_ce_mention = False
    for term in CE_KEYWORDS:
        start = 0
        while True:
            idx = text.find(term, start)
            if idx == -1:
                break
            found_any_ce_mention = True

            ctx_start = max(0, idx - CONTEXT_WINDOW)
            ctx_end = min(len(text), idx + len(term) + CONTEXT_WINDOW)
            context = text[ctx_start:ctx_end]

            has_stock = any(kw in context for kw in KEYWORDS_IN_STOCK)
            has_sold_out = any(kw in context for kw in KEYWORDS_SOLD_OUT)

            if has_stock and not has_sold_out:
                print(f"[ALARM] {site}: Treffer auf '{term}'")
                send_discord_alert(site, url, term)
                send_email_alert(site, url, term)
                return
            start = idx + len(term)

    if found_any_ce_mention:
        print(f"[INFO] {site}: CE erwähnt, aber kein Verfügbarkeits-Hinweis in der Nähe.")
    else:
        print(f"[INFO] {site}: Keine Collector's-Edition-Erwähnung gefunden.")


def main():
    print("=== GTA 6 CE Check ===")
    for site, url in URLS.items():
        check_site(site, url)
    print("=== Check abgeschlossen ===")


if __name__ == "__main__":
    main()
