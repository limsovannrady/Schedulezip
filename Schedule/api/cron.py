import asyncio
import os
import sys
from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot_core import build_application, check_scheduled_messages


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        try:
            async def run():
                app = build_application(with_job_queue=False)
                await app.initialize()
                ctx = SimpleNamespace(bot=app.bot)
                await check_scheduled_messages(ctx)
                await app.shutdown()

            asyncio.run(run())

            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
        except Exception as e:
            print(f"[Cron] Error: {e}")
            self.send_response(500)
            self.end_headers()
            self.wfile.write(b"Internal Server Error")

    def log_message(self, format, *args):
        pass
