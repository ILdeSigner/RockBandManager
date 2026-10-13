from http.server import BaseHTTPRequestHandler
import json
import os
import sys

# Umożliwienie importu skryptu z katalogu głównego
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rock_booking_engine import run_scraper, send_email_report

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
            output_csv = "/tmp/kontakty_booking.csv"
            contacts = run_scraper(output_csv=output_csv)
            send_email_report(output_csv, contacts)

            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {
                "success": True,
                "message": f"Przeskanowano i wysłano raport z {len(contacts)} kontaktami.",
                "contacts_count": len(contacts)
            }
            self.wfile.write(json.dumps(response).encode('utf-8'))
        except Exception as e:
            self.send_response(500)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"error": str(e)}).encode('utf-8'))
