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

@dataclass
class ManagerCandidate:
    name: str
    location: str
    role_type: str
    website: str
    email: str
    phone: str
    notes: str
    source_query: str

# -------------------------------------------------------------
# Zapytania 1: Kluby i Miejsca do Grania na Żywo (Wrocław + 200 km)
# -------------------------------------------------------------
VENUE_SEARCH_QUERIES = [
    # Kluby i puby rockowe (live music)
    'klub rockowy muzyka na żywo koncerty booking kontakt Wrocław',
    'pub rockowy koncerty na żywo Dolny Śląsk booking mail',
    'klub muzyczny koncerty rockowe Legnica Wałbrzych Jelenia Góra booking',
    'kluby z muzyką na żywo Opole Brzeg Nysa koncerty mail',
    'klub rockowy koncerty Leszno Ostrów Wielkopolski Kalisz booking mail',
    'pub muzyczny koncerty Zielona Góra Nowa Sól Żary kontakt mail',
    'klub muzyczny koncerty Świdnica Dzierżoniów Kłodzko booking',
    
    # Domy i Ośrodki Kultury (MOK, GOK, CKiS, WCK)
    'ośrodek kultury koncerty zespoły rockowe zgłoszenia Dolny Śląsk',
    'MOK WCK GOK koncerty rock booking kontakt dolnośląskie',
    'miejski dom kultury koncerty dni miasta booking zespołów Dolny Śląsk Opole',
    'centrum kultury koncerty muzyka na żywo kontakt booking Wrocław okolice',
    
    # Festiwale, przeglądy, zloty motocyklowe i imprezy plenerowe
    'zlot motocyklowy koncerty zespołów rockowych zgłoszenia Dolny Śląsk',
    'festiwal rockowy przegląd kapel zgłoszenia zespołów Dolny Śląsk',
    'festiwal rockowy zlot motocyklowy muzyka na żywo Opolszczyzna Lubuskie',
    'plenerowe koncerty rockowe festiwal zlot Dolny Śląsk Wielkopolska kontakt'
]

# -------------------------------------------------------------
# Zapytania 2: Menedżerowie, Agencje Bookingowe i Bookerzy (Płatne Koncerty)
# -------------------------------------------------------------
MANAGER_SEARCH_QUERIES = [
    'menedżer zespołu rockowego współpraca kontakt booking Polska',
    'agencja bookingowa zespoły rockowe organizacja koncertów kontakt',
    'manager muzyczny impresariat koncerty zespoły rock kontakt mail',
    'booker koncertowy organizacja płatnych koncertów zespoły rockowe Wrocław',
    'menadżer kapeli rockowej poszukiwany ogłoszenia kontakt',
    'impresario muzyczny management zespołów rockowych booking Polska kontakt'
]

IGNORED_DOMAINS = {
    'google.com', 'google.pl', 'duckduckgo.com', 'youtube.com', 'facebook.com', 
    'instagram.com', 'twitter.com', 'x.com', 'wikipedia.org', 'trojmiasto.pl',
    'olx.pl', 'allegro.pl', 'gowork.pl', 'linkedin.com', 'tiktok.com', 'pinterest.com'
}

def search_duckduckgo_fallback(query: str, num_results: int = 12) -> List[Dict[str, str]]:
    """Darmowe, dynamiczne wyszukiwanie DuckDuckGo."""
    targets = []
    try:
        url = f"https://html.duckduckgo.com/html/?q={urllib.parse.quote(query)}"
        resp = requests.post(url, headers=HEADERS, timeout=12)
        if resp.status_code == 200:
            soup = BeautifulSoup(resp.text, 'html.parser')
            for a in soup.select('.result__title a.result__url, a.result__snippet'):
                href = a.get('href', '')
                if 'uddg=' in href:
                    parsed_link = urllib.parse.unquote(href.split('uddg=')[1].split('&')[0])
                else:
                    parsed_link = href
                title = a.get_text(strip=True)
                if parsed_link and parsed_link.startswith('http'):
                    domain = urllib.parse.urlparse(parsed_link).netloc.lower()
                    if not any(ign in domain for ign in IGNORED_DOMAINS):
                        targets.append({"title": title or domain, "link": parsed_link})
                if len(targets) >= num_results:
                    break
    except Exception as e:
        print(f"[!] Błąd DuckDuckGo dla query '{query}': {e}")
    return targets

def search_web_targets(query: str, num_results: int = 12) -> List[Dict[str, str]]:
    """Wyszukuje strony w sieci przez SerpAPI lub DuckDuckGo."""
    targets = []
    if SERPAPI_KEY:
        try:
            url = f"https://serpapi.com/search.json?q={urllib.parse.quote(query)}&hl=pl&gl=pl&num={num_results}&api_key={SERPAPI_KEY}"
            res = requests.get(url, timeout=12).json()
            for r in res.get("organic_results", []):
                link = r.get("link", "")
                domain = urllib.parse.urlparse(link).netloc.lower()
                if not any(ign in domain for ign in IGNORED_DOMAINS):
                    targets.append({"title": r.get("title", domain), "link": link})
            if targets:
                return targets
        except Exception as e:
            print(f"[!] Błąd SerpAPI dla query '{query}': {e}")
    
    return search_duckduckgo_fallback(query, num_results=num_results)

def scrape_page_contacts(url: str) -> Tuple[str, str]:
    """Przeszukuje domenę docelową i podstrony kontaktu pod kątem e-maili i telefonów."""
    emails: Set[str] = set()
    phones: Set[str] = set()

    subpages = ["", "/kontakt", "/contact", "/booking", "/o-nas", "/koncerty", "/zespoly", "/organizacja-imprez"]
    for sub in subpages:
        target = urllib.parse.urljoin(url, sub)
        try:
            resp = requests.get(target, headers=HEADERS, timeout=6)
            if resp.status_code != 200:
                continue
            soup = BeautifulSoup(resp.text, 'html.parser')
            text = soup.get_text()

            for a in soup.select('a[href^="mailto:"]'):
                e = a.get('href', '').replace('mailto:', '').split('?')[0].strip()
                if EMAIL_REGEX.match(e):
                    emails.add(e)
            for a in soup.select('a[href^="tel:"]'):
                p = a.get('href', '').replace('tel:', '').strip()
                phones.add(p)

            for e in EMAIL_REGEX.findall(text):
                if not any(e.lower().endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.svg', '.js', '.css', '.webp', '.gif']):
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

def determine_city_and_category(title: str, query: str, domain: str) -> Tuple[str, str]:
    """Automatyczne określenie lokalizacji w promieniu 200 km i formatu miejsca."""
    full_str = f"{title} {query} {domain}".lower()
    cities = [
        "wrocław", "legnica", "wałbrzych", "jelenia góra", "opole", "brzeg", "nysa",
        "zielona góra", "nowa sól", "żary", "żagań", "leszno", "ostrów wielkopolski",
        "kalisz", "świdnica", "dzierżoniów", "kłodzko", "oleśnica", "oława", "lubin",
        "głogów", "bolesławiec", "zgorzelec", "bielawa", "jawor", "kędzierzyn-koźle"
    ]
    detected_city = "Wrocław (promień 200 km)"
    for c in cities:
        if c in full_str:
            detected_city = c.capitalize()
            break

    if any(k in full_str for k in ["zlot", "motocykl", "moto"]):
        cat = "Zlot Motocyklowy / Impreza Moto"
    elif any(k in full_str for k in ["festiwal", "przegląd", "festiwalu"]):
        cat = "Festiwal Rockowy / Plener"
    elif any(k in full_str for k in ["mok", "gok", "wck", "ckis", "ośrodek kultury", "dom kultury", "centrum kultury"]):
        cat = "Ośrodek Kultury / Dom Kultury"
    else:
        cat = "Klub Muzyczny / Pub Rockowy"

    return detected_city, cat

# -------------------------------------------------------------
# Moduł 1: Scrapowanie Miejsc na Koncerty (Promień 200km Wrocław)
# -------------------------------------------------------------
def run_venue_scraper(output_csv: str = "kontakty_booking.csv") -> List[BookingContact]:
    print("[*] Skanowanie klubów, domów kultury i festiwali w promieniu 200 km od Wrocławia...")
    contacts: List[BookingContact] = []
    seen_domains = set()

    for q in VENUE_SEARCH_QUERIES:
        found_links = search_web_targets(q, num_results=10)
        for item in found_links:
            link = item.get("link", "")
            if not link:
                continue
            parsed_domain = urllib.parse.urlparse(link).netloc.lower()
            if not parsed_domain or parsed_domain in seen_domains:
                continue
            seen_domains.add(parsed_domain)

            scheme = urllib.parse.urlparse(link).scheme or "https"
            base_url = f"{scheme}://{parsed_domain}"
            mail, phone = scrape_page_contacts(base_url)
            city, category = determine_city_and_category(item['title'], q, parsed_domain)

            contact = BookingContact(
                name=item["title"],
                city=city,
                category=category,
                website=base_url,
                email=mail if mail else "Do uzupełnienia (FB/formularz)",
                phone=phone if phone else "Brak",
                source_query=q
            )
            contacts.append(contact)

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "city", "category", "website", "email", "phone", "source_query"
        ])
        writer.writeheader()
        for c in contacts:
            writer.writerow(asdict(c))

    print(f"[+] Zapisano {len(contacts)} miejsc koncertowych do pliku {output_csv}")
    return contacts

# -------------------------------------------------------------
# Moduł 2: Dynamiczne Wyszukiwanie Menedżerów i Agencji Bookingowych
# -------------------------------------------------------------
def run_manager_scout(output_csv: str = "kandydaci_menedzerowie.csv") -> List[ManagerCandidate]:
    print("\n[*] Przeszukiwanie sieci w poszukiwaniu menedżerów i bookerów dla kapeli rockowej...")
    managers: List[ManagerCandidate] = []
    seen_domains = set()

    for q in MANAGER_SEARCH_QUERIES:
        found_links = search_web_targets(q, num_results=10)
        for item in found_links:
            link = item.get("link", "")
            if not link:
                continue
            parsed_domain = urllib.parse.urlparse(link).netloc.lower()
            if not parsed_domain or parsed_domain in seen_domains:
                continue
            seen_domains.add(parsed_domain)

            scheme = urllib.parse.urlparse(link).scheme or "https"
            base_url = f"{scheme}://{parsed_domain}"
            mail, phone = scrape_page_contacts(base_url)

            role_type = "Agencja Bookingowa / Management" if any(w in (item['title'] + q).lower() for w in ["agencja", "management", "impresariat"]) else "Niezależny Menedżer / Booker"
            location = "Wrocław / Dolny Śląsk" if "wrocław" in (item['title'] + q).lower() else "Polska / Zdalnie"

            candidate = ManagerCandidate(
                name=item["title"],
                location=location,
                role_type=role_type,
                website=base_url,
                email=mail if mail else "Do kontaktu przez stronę/formularz",
                phone=phone if phone else "Brak",
                notes="Organizacja płatnych koncertów rockowych / rev-share",
                source_query=q
            )
            managers.append(candidate)

    with open(output_csv, mode="w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "name", "location", "role_type", "website", "email", "phone", "notes", "source_query"
        ])
        writer.writeheader()
        for m in managers:
            writer.writerow(asdict(m))

    print(f"[+] Zapisano {len(managers)} potencjalnych menedżerów/agencji do pliku {output_csv}")
    return managers

# -------------------------------------------------------------
# Moduł 3: Rekrutacja Menedżera (Post)
# -------------------------------------------------------------
RECRUITMENT_POST_TEMPLATE = """
[SZUKAMY OGARNIACZA / PROMOTORA / BOOKERA DLA ZESPOŁU ROCKOWEGO]
Lokalizacja: Wrocław / Promień 200 km / Zdalnie

Gramy energetycznego, koncertowego rocka i szukamy zmotywowanej osoby, która dołączy do teamu i pomoże nam rozwinąć skrzydła koncertowo!

Czym będziesz się zajmować:
🎸 Bezpośrednim kontaktem z klubami rockowymi, festiwalami, domami kultury i zlotami motocyklowymi,
📅 Dogadywaniem terminów płatnych koncertów, supportów i riderów technicznych,
📋 Pilnowaniem kalendarza występów i promocji wydarzeń.

Rozliczenie i korzyści:
💰 Prowizyjny podział: ustalony procent od każdej wynegocjowanej gaży za koncert (% zależny od zaangażowania),
🎯 Opcja dla pasjonata / studenta chcącego zdobyć realne portfolio i kontakty w branży muzycznej (management/booking),
🔥 Dostęp do zaplecza zespołu, backstage'u i wspólnych wyjazdów.

Jeśli kręci Cię scena koncertowa, masz łatwość w pisaniu maili i dzwonieniu do klubów – odezwij się do nas w wiadomości prywatnej!
"""

def generate_recruitment_package(output_file: str = "ogloszenie_menedzer_zespolu.txt"):
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(RECRUITMENT_POST_TEMPLATE.strip())
    print(f"[+] Wygenerowano gotowy post rekrutacyjny w: {output_file}")

# -------------------------------------------------------------
# Moduł 4: Wysyłka Raportu E-mail (Miejsca + Kandydaci na Menedżera)
# -------------------------------------------------------------
def send_email_report(
    venues_csv: str, 
    venues: List[BookingContact], 
    managers_csv: str = None, 
    managers: List[ManagerCandidate] = None
):
    if not (SMTP_USER and SMTP_PASSWORD):
        print("[!] Brak skonfigurowanych zmiennych SMTP. Pomijanie wysyłki maila.")
        return

    managers = managers or []
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = RECIPIENT_EMAIL
    msg['Subject'] = f"🎸 Piątkowy Raport: {len(venues)} Miejsc Koncertowych + {len(managers)} Menedżerów/Agencji"

    venue_rows = "".join([
        f"<tr><td><strong>{c.name}</strong></td><td>{c.city}</td><td>{c.category}</td><td><a href='{c.website}'>{c.website}</a></td><td>{c.email}</td><td>{c.phone}</td></tr>"
        for c in venues[:20]
    ])

    manager_rows = "".join([
        f"<tr><td><strong>{m.name}</strong></td><td>{m.location}</td><td>{m.role_type}</td><td><a href='{m.website}'>{m.website}</a></td><td>{m.email}</td><td>{m.phone}</td></tr>"
        for m in managers[:10]
    ]) if managers else "<tr><td colspan='6'>Brak nowych kandydatów w tym przebiegu.</td></tr>"

    html_body = f"""
    <html>
      <body style="font-family: Arial, sans-serif; color: #222; line-height: 1.5; padding: 15px;">
        <h2 style="color: #d63031;">🎸 Raport Muzyczny: Miejsca Live + Poszukiwanie Menedżera</h2>
        <p>Cześć! Zakończono automatyczne cotygodniowe skanowanie sieci:</p>
        
        <ul>
          <li><strong>Miejsca na koncerty (promień 200 km od Wrocławia):</strong> {len(venues)} klubów, MOK-ów, festiwali i zlotów</li>
          <li><strong>Potencjalni menedżerowie / agencje bookingowe:</strong> {len(managers)} kontaktów do pozyskiwania płatnych koncertów</li>
        </ul>

        <h3 style="border-bottom: 2px solid #0984e3; padding-bottom: 5px;">🎯 Menedżerowie i Agencje Bookingowe (Płatne Koncerty):</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; border-color: #ddd; width: 100%; font-size: 13px; margin-bottom: 25px;">
          <tr style="background: #0984e3; color: #fff;">
            <th>Nazwa / Agencja</th><th>Lokalizacja</th><th>Typ</th><th>Strona WWW</th><th>Email</th><th>Telefon</th>
          </tr>
          {manager_rows}
        </table>

        <h3 style="border-bottom: 2px solid #d63031; padding-bottom: 5px;">🏢 Miejsca Koncertowe (Wrocław + 200 km):</h3>
        <table border="1" cellpadding="6" cellspacing="0" style="border-collapse: collapse; border-color: #ddd; width: 100%; font-size: 13px;">
          <tr style="background: #2d3436; color: #fff;">
            <th>Nazwa Miejsca</th><th>Miasto</th><th>Kategoria</th><th>Strona WWW</th><th>Email</th><th>Telefon</th>
          </tr>
          {venue_rows}
        </table>

        <p style="margin-top: 20px; font-size: 12px; color: #636e72;">
          <i>Kompletne bazy kontaktów zostały załączone do wiadomości w plikach CSV.</i>
        </p>
      </body>
    </html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    # Załączniki CSV
    for filepath in [venues_csv, managers_csv]:
        if filepath and os.path.exists(filepath):
            with open(filepath, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename="{os.path.basename(filepath)}"')
                msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
            print(f"[+] Raport e-mail z powiadomieniem wysłany pomyślnie na adres: {RECIPIENT_EMAIL}")
    except Exception as e:
        print(f"[!] Błąd wysyłania e-maila: {e}")

# -------------------------------------------------------------
# Moduł CLI
# -------------------------------------------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Rock Booking & Manager Scout Engine")
    parser.add_argument("--mode", choices=["all", "venues", "managers", "recruit", "email"], default="all",
                        help="Tryb: all, venues, managers, recruit, email")
    parser.add_argument("--venues-csv", default="kontakty_booking.csv", help="Ścieżka do CSV z klubami")
    parser.add_argument("--managers-csv", default="kandydaci_menedzerowie.csv", help="Ścieżka do CSV z menedżerami")
    args = parser.parse_args()

    venues_list = []
    managers_list = []

    if args.mode in ["all", "venues"]:
        venues_list = run_venue_scraper(args.venues_csv)

    if args.mode in ["all", "managers"]:
        managers_list = run_manager_scout(args.managers_csv)

    if args.mode in ["all", "recruit"]:
        generate_recruitment_package()

    if args.mode in ["all", "email"]:
        if not venues_list and os.path.exists(args.venues_csv):
            with open(args.venues_csv, mode="r", encoding="utf-8") as f:
                venues_list = [BookingContact(**r) for r in csv.DictReader(f)]
        if not managers_list and os.path.exists(args.managers_csv):
            with open(args.managers_csv, mode="r", encoding="utf-8") as f:
                managers_list = [ManagerCandidate(**r) for r in csv.DictReader(f)]
        send_email_report(args.venues_csv, venues_list, args.managers_csv, managers_list)
