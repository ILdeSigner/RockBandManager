import os
import re
import csv
import smtplib
import argparse
import urllib.parse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dataclasses import dataclass, asdict
from typing import List, Set, Dict, Any, Tuple
import requests
from bs4 import BeautifulSoup

# --- Konfiguracja i Zmienne Środowiskowe ---
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "")
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", SMTP_USER)

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+')
PHONE_REGEX = re.compile(r'(?:\+?48)?(?:\s*\(?0\)?\s*)?[1-9]\d{1,2}(?:[\s.-]?\d{3}){2}|(?:\+?48)?\s*\d{3}[\s.-]?\d{3}[\s.-]?\d{3}')

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

@dataclass
class BookingContact:
    name: str
    city: str
    category: str
    website: str
    email: str
    phone: str
    source_query: str

# -------------------------------------------------------------
# Moduł 1: Dynamiczne wyszukiwanie (SerpAPI lub DuckDuckGo / fallback web)
# -------------------------------------------------------------
SEARCH_QUERIES = [
    'organizator koncertów rockowych Wrocław booking kontakt mail',
    'kluby rockowe Dolny Śląsk koncerty booking mail',
    'agencja bookingowa zespoły rockowe Polska kontakt',
    'menedżer zespołu rockowego ogłoszenia współpraca Polska',
    'festiwale rockowe motocyklowe zgłoszenia zespołów Dolny Śląsk'
]

def search_duckduckgo_fallback(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Darmowy fallback bez klucza API wykorzystujący HTML DuckDuckGo."""
    targets = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        resp = requests.post(url, headers=HEADERS, timeout=10)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.select('.result__title a.result__url, a.result__snippet')[:num_results]:
                href = a.get('href', '')
                if 'uddg=' in href:
                    parsed_link = urllib.parse.unquote(href.split('uddg=')[1].split('&')[0])
                else:
                    parsed_link = href
                title = a.get_text(strip=True)
                if parsed_link and parsed_link.startswith('http'):
                    targets.append({"title": title or "Link z wyszukiwarki", "link": parsed_link})
    except Exception as e:
        print(f"[!] Błąd fallback DuckDuckGo dla query '{query}': {e}")
    return targets

def search_web_targets(query: str, num_results: int = 5) -> List[Dict[str, str]]:
    """Wyszukuje strony docelowe przez SerpAPI lub darmowy fallback."""
    targets = []
    if SERPAPI_KEY:
        try:
            url = f"https://serpapi.com/search.json?q={urllib.parse.quote(query)}&hl=pl&gl=pl&api_key={SERPAPI_KEY}"
            res = requests.get(url, timeout=10).json()
            for r in res.get("organic_results", [])[:num_results]:
                targets.append({"title": r.get("title", ""), "link": r.get("link", "")})
            return targets
        except Exception as e:
            print(f"[!] Błąd SerpAPI dla query '{query}': {e}")
    
    # Próba DuckDuckGo
    ddg_targets = search_duckduckgo_fallback(query, num_results)
    if ddg_targets:
        return ddg_targets

    # Domyślne domeny awaryjne
    return [
        {"title": "Stary Klasztor Wrocław", "link": "http://staryklasztor.com.pl"},
        {"title": "Liverpool Wrocław", "link": "http://liverpool.wroclaw.pl"},
        {"title": "CK Wiatrak Zabrze", "link": "https://wiatrak.art.pl"},
        {"title": "Hydrozagadka Warszawa", "link": "https://hydrozagadka.waw.pl"}
    ]

def scrape_page_contacts(url: str) -> Tuple[str, str]:
    """Przeszukuje domenę i zakładki /kontakt pod kątem maili i telefonów."""
    emails: Set[str] = set()
    phones: Set[str] = set()

    for sub in ["", "/kontakt", "/contact", "/booking"]:
        target = urllib.parse.urljoin(url, sub)
        try:
            resp = requests.get(target, headers=HEADERS, timeout=6)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()

            # Szukanie w href mailto / tel
            for a in soup.select('a[href^="mailto:"]'):
                e = a.get('href', '').replace('mailto:', '').split('?')[0].strip()
                if EMAIL_REGEX.match(e):
                    emails.add(e)
            for a in soup.select('a[href^="tel:"]'):
                p = a.get('href', '').replace('tel:', '').strip()
                phones.add(p)

            # Szukanie w tekście
            for e in EMAIL_REGEX.findall(text):
                if not any(e.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg', '.js', '.css', '.webp']):
                    emails.add(e.lower())
            for p in PHONE_REGEX.findall(text):
                cleaned = re.sub(r'[^\d+]', '', p)
                if len(cleaned) >= 9:
                    phones.add(p.strip())
        except Exception:
            continue

    primary_email = next(iter(emails), "")
    primary_phone = next(iter(phones), "")
    return primary_email, primary_phone

def run_scraper(output_csv: str = "kontakty_booking.csv") -> List[BookingContact]:
    print("[*] Uruchamianie wyszukiwarki organizatorów i klubów...")
    contacts: List[BookingContact] = []
    seen_urls = set()

    for q in SEARCH_QUERIES:
        found_links = search_web_targets(q)
        for item in found_links:
            link = item.get("link", "")
            if not link:
                continue
            parsed_domain = urllib.parse.urlparse(link).netloc
            if not parsed_domain or parsed_domain in seen_urls:
                continue
            seen_urls.add(parsed_domain)

            print(f" -> Analiza: {item['title']} ({parsed_domain})")
            scheme = urllib.parse.urlparse(link).scheme or "https"
            base_url = f"{scheme}://{parsed_domain}"
            mail, phone = scrape_page_contacts(base_url)

            city = "Wrocław / Dolny Śląsk" if any(w in (item['title'] + q).lower() for w in ["wrocław", "dolny", "legnica", "wałbrzych"]) else "Polska"

            contact = BookingContact(
                name=item["title"],
                city=city,
                category="Klub / Booker / Festiwal",
                website=base_url,
                email=mail if mail else "Do uzupełnienia (FB/formularz)",
                phone=phone if phone else "Brak",
                source_query=q
            )
            contacts.append(contact)

    # Zapis do CSV
    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "city", "category", "website", "email", "phone", "source_query"
        ])
        writer.writeheader()
        for c in contacts:
            writer.writerow(asdict(c))

    print(f"[+] Zapisano {len(contacts)} rekordów do pliku {output_csv}")
    return contacts

# -------------------------------------------------------------
# Moduł 2: Rekrutacja menedżera / „ogarniacza” kapeli (% od koncertu)
# -------------------------------------------------------------
RECRUITMENT_POST_TEMPLATE = """
[SZUKAMY OGARNIACZA / PROMOTORA / BOOKERA DLA ZESPOŁU ROCKOWEGO]
Lokalizacja: Wrocław / Dolny Śląsk / Zdalnie

Gramy energetycznego rocka i szukamy osoby, która dołączy do teamu i zajmie się:
- kontaktem z klubami rockowymi, festiwalami i domami kultury,
- dogadywaniem terminów koncertów i riderów technicznych,
- pilnowaniem kalendarza występów.

Rozliczenie:
- Prowizyjny podział: ustalony procent od każdej wynegocjowanej gaży za koncert (% zależny od zaangażowania)
- Opcja dla pasjonata / studenta chcącego zdobyć realne portfolio w branży muzycznej (management/booking).

Jeśli kręci Cię scena koncertowa, masz łatwość w pisaniu maili i dzwonieniu do klubów – odezwij się do nas!
"""

def generate_recruitment_package(output_file: str = "ogloszenie_menedzer_zespolu.txt"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(RECRUITMENT_POST_TEMPLATE.strip())
    print(f"[+] Wygenerowano gotowy post rekrutacyjny w: {output_file}")

# -------------------------------------------------------------
# Moduł 3: Wysyłka raportu i powiadomień e-mail
# -------------------------------------------------------------
def send_email_report(csv_filepath: str, contacts: List[BookingContact]):
    if not (SMTP_USER and SMTP_PASSWORD):
        print("[!] Brak skonfigurowanych zmiennych SMTP. Pomijanie wysyłki maila.")
        return

    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"🎸 Cotygodniowy Raport Bookingowy Rock – {len(contacts)} nowych kontaktów"

    table_rows = "".join([
        f"<tr><td>{c.name}</td><td>{c.city}</td><td><a href='{c.website}'>{c.website}</a></td><td>{c.email}</td><td>{c.phone}</td></tr>"
        for c in contacts[:15]
    ])

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #333;">
        <h2>Cotygodniowy Raport Bookingowy</h2>
        <p>Cześć! Twój agent zebrał <strong>{len(contacts)} kontaktów</strong> do klubów, bookerów i organizatorów.</p>
        
        <h3>Podgląd pierwszych kontaktów:</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; border-color: #ddd;">
          <tr style="background: #f4f4f4;">
            <th>Nazwa</th><th>Miasto</th><th>Strona</th><th>Email</th><th>Telefon</th>
          </tr>
          {table_rows}
        </table>
        <p><i>Pełna baza znajduje się w załączonym pliku CSV.</i></p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    # Załącznik CSV
    if os.path.exists(csv_filepath):
        with open(csv_filepath, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(csv_filepath)}"')
            msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"[+] Raport e-mail wysłany pomyślnie na adres: {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"[!] Błąd wysyłania e-maila: {e}")

# -------------------------------------------------------------
# Moduł CLI – uruchamianie dowolnej części osobno
# -------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rock Booking & Outreach Engine")
    parser.add_argument("--mode", choices=["all", "scrape", "recruit", "email"], default="all",
                        help="Tryb: scrape (zbieranie kontaktów), recruit (post rekrutacyjny), email (wysyłka), all (pełen obieg)")
    parser.add_argument("--csv", default="kontakty_booking.csv", help="Ścieżka do pliku CSV")
    args = parser.parse_args()

    collected = []
    if args.mode in ["all", "scrape"]:
        collected = run_scraper(args.csv)

    if args.mode in ["all", "recruit"]:
        generate_recruitment_package()

    if args.mode in ["all", "email"]:
        if not collected and os.path.exists(args.csv):
            with open(args.csv, mode="r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                collected = [BookingContact(**r) for r in reader]
        send_email_report(args.csv, collected)
