from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Umożliwienie importu skryptu z katalogu głównego
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rock_booking_engine import run_venue_scraper, run_manager_scout, send_email_report

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        # Sprawdzanie tokena autoryzacji CRON_SECRET (zabezpieczenie Vercel)
        cron_secret = os.getenv("CRON_SECRET", "")
        auth_header = self.headers.get("Authorization", "")

        if cron_secret and auth_header != f"Bearer {cron_secret}":
            self.send_response(401)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": "Unauthorized"}).encode('utf-8'))
            return

        try:
            # Pliki tymczasowe w środowisku bezserwerowym Vercel
            venues_csv = "/tmp/kontakty_booking.csv"
            managers_csv = "/tmp/kandydaci_menedzerowie.csv"

            # 1. Przeszukanie miejsc koncertowych (Wrocław + 200 km)
            venues = run_venue_scraper(output_csv=venues_csv)

            # 2. Przeszukanie menedżerów i agencji bookingowych pod kątem płatnych koncertów
            managers = run_manager_scout(output_csv=managers_csv)

            # 3. Wysłanie powiadomienia e-mail z raportem i załącznikami CSV
            send_email_report(
                venues_csv=venues_csv,
                venues=venues,
                managers_csv=managers_csv,
                managers=managers
            )

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "success": True,
                "message": f"Przeskanowano sieć! Znaleziono {len(venues)} miejsc koncertowych i {len(managers)} menedżerów/agencji. Wysłano e-mail.",
                "venues_count": len(venues),
                "managers_count": len(managers)
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
