import asyncio
import json
import os
import sys
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from bot_core import build_application


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)
            update_data = json.loads(body)

            async def process():
                app = build_application(with_job_queue=False)
                await app.initialize()
                update = Update.de_json(update_data, app.bot)
                await app.process_update(update)
                await app.shutdown()

            asyncio.run(process())

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            print(f"[Webhook] Error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal Server Error")

    def log_message(self, format, *args):
        pass
