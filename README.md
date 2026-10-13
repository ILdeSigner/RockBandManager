# 🎸 Rock Booking & Manager Outreach Engine

Zautomatyzowany silnik wyszukiwania kontaktów do klubów, bookerów, agencji i organizatorów festiwali rockowych wraz z modułem rekrutacji menedżera kapeli na prowizji.

---

## 🌐 Aplikacja Webowa (GitHub Pages)

W projekcie znajduje się gotowa aplikacja [`index.html`](file:///index.html), którą możesz uruchomić bez serwera bezpośrednio przez **GitHub Pages**:
- **Zakładka 1: Baza Kontaktów (CRM)** – przeglądanie klubów, filtrowanie (Wrocław / Dolny Śląsk / Polska), statusy bookingu, import/eksport CSV.
- **Zakładka 2: Wyszukiwarka & Scraper** – bezpośrednie zapytania Google dorking do klubów rockowych + regex parser wyciągający maile i telefony z wklejonego tekstu.
- **Zakładka 3: Generator Mailingu & Pitch** – spersonalizowane szablony ofert koncertowych z generowaniem linku `mailto:` jednym kliknięciem.
- **Zakładka 4: Rekrutacja Menedżera** – gotowy post na grupy FB / LinkedIn / OLX w modelu rev-share (% od koncertu).
- **Zakładka 5: GitHub Cron & CLI** – ściąga z komend CLI i instrukcja GitHub Actions.

### Jak włączyć GitHub Pages:
1. Wypchnij kod na GitHub (`git push`).
2. Przejdź do: **Settings -> Pages**.
3. W sekcji **Build and deployment -> Source** wybierz `Deploy from a branch`.
4. Wybierz gałąź `main` (lub `master`) oraz folder `/(root)` i kliknij **Save**.
5. Twoja strona będzie dostępna pod adresem: `https://<twoj-login>.github.io/<nazwa-repozytorium>/`.

---

## 🚀 Opcje Uruchomienia w Chmurze (Zalecane darmowe usługi)

### 🥇 Opcja A (Najlepsza i bez limitów timeoutu): **GitHub Actions**
- **Dlaczego:** Masz już konto GitHub. GitHub Actions daje **2000 darmowych minut miesięcznie** dla prywatnych repozytoriów (i nielimitowane dla publicznych).
- **Zaleta:** Brak limitów 10-sekundowego timeoutu (które ma Vercel Hobby Free). Scrapowanie wielu domen może trwać 30–60 sekund, co na GitHub Actions wykona się bez problemu.
- **Konfiguracja:**
  1. Wejdź w repozytorium na GitHubie -> `Settings` -> `Secrets and variables` -> `Actions`.
  2. Dodaj Repository Secrets:
     - `SMTP_USER` (Twój Gmail)
     - `SMTP_PASSWORD` (Hasło aplikacji Google App Password)
     - `RECIPIENT_EMAIL` (Twój adres docelowy)
     - `SERPAPI_KEY` (Opcjonalny klucz z SerpAPI)
  3. Workflow jest już w [`.github/workflows/weekly_booking.yml`](file:///.github/workflows/weekly_booking.yml). Możesz go odpalić ręcznie w zakładce **Actions -> Run workflow** lub poczekać na poniedziałkowy harmonogram.

---

### 🥈 Opcja B: **Vercel Cron**
- **Konfiguracja:**
  - Plik konfiguracyjny: [`vercel.json`](file:///vercel.json) z cronem `0 9 * * 1`.
  - Endpoint Serverless Python: [`api/cron.py`](file:///api/cron.py).
  - W panelu Vercel -> *Settings* -> *Environment Variables* dodaj:
    - `SMTP_USER`, `SMTP_PASSWORD`, `RECIPIENT_EMAIL`, `SERPAPI_KEY`, `CRON_SECRET`.
- *Uwaga:* Darmowy plan Vercel Hobby ma 10-15s timeout na funkcję bezpłatną.

---

## 🛠️ Uruchamianie lokalne (CLI)

Zainstaluj zależności:
```bash
pip install -r requirements.txt
```

Uruchomienie wybranego modułu:
```bash
# 1. Tylko scraping kontaktów do CSV:
python rock_booking_engine.py --mode scrape

# 2. Tylko generowanie ogłoszenia rekrutacyjnego dla menedżera:
python rock_booking_engine.py --mode recruit

# 3. Tylko wysyłka ostatnio zebranych kontaktów na e-mail:
python rock_booking_engine.py --mode email

# 4. Pełen cykl (scraping + generowanie posta + wysyłka raportu):
python rock_booking_engine.py --mode all
```

---

## 🔑 Darmowe usługi z wysokimi limitami:

1. **SerpAPI (serpapi.com)** – 100 zapytań/miesięcznie za darmo (wystarcza na cotygodniowy cron).
2. **Resend (resend.com)** – jeśli nie chcesz używać Gmail SMTP, darmowe 3000 maili/miesięcznie (100 dziennie) przez proste API.
3. **Gmail SMTP** – w 100% darmowe (do 500 maili/dzień). Wystarczy włączyć 2FA na koncie Google i wygenerować *Hasło do aplikacji (App Password)*.
