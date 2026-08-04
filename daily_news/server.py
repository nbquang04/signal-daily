"""Dependency-free API and static frontend server."""

import argparse
import json
import mimetypes
import re
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from .storage import archive_dates, database_dates, get_archived_report, get_database_report, list_archives


class NewsHandler(BaseHTTPRequestHandler):
    database = Path("data/daily_news.db")
    archive_dir = Path("data/archives")
    web_dir = Path("web")
    refresh_hours = 5.0

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if self.path.startswith("/api/") else "public, max-age=300")
        self.end_headers()
        self.wfile.write(body)

    def _static(self, request_path: str):
        relative = "index.html" if request_path in ("", "/") else request_path.lstrip("/")
        root = self.web_dir.resolve()
        target = (root / relative).resolve()
        if root not in target.parents and target != root:
            return self._json({"error": "not found"}, 404)
        if not target.is_file():
            target = root / "index.html"
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(target.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path == "/api/health":
            dates = database_dates(self.database)
            return self._json({"status": "ok", "database": str(self.database), "active_reports": len(dates), "latest": dates[0] if dates else None, "refresh_hours": self.refresh_hours})
        if path == "/api/editions":
            dates = sorted(set(database_dates(self.database) + archive_dates(self.archive_dir)), reverse=True)
            return self._json({"dates": dates, "latest": dates[0] if dates else None})
        if path == "/api/archives":
            return self._json({"archives": list_archives(self.database, self.archive_dir)})
        match = re.fullmatch(r"/api/editions/(\d{4}-\d{2}-\d{2})", path)
        if match:
            report_date = match.group(1)
            payload = get_database_report(self.database, report_date) or get_archived_report(self.archive_dir, report_date)
            return self._json(payload, 200) if payload else self._json({"error": "edition not found"}, 404)
        if path.startswith("/api/"):
            return self._json({"error": "not found"}, 404)
        return self._static(path)

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    parser = argparse.ArgumentParser(description="Serve Signal Daily API and frontend")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--database", type=Path, default=Path("data/daily_news.db"))
    parser.add_argument("--archives", type=Path, default=Path("data/archives"))
    parser.add_argument("--web", type=Path, default=Path("web"))
    parser.add_argument("--refresh-hours", type=float, default=5.0, help="Run the collection pipeline periodically; use 0 to disable")
    parser.add_argument("--no-refresh-on-start", action="store_true", help="Wait for the first interval instead of refreshing at startup")
    args = parser.parse_args()
    NewsHandler.database, NewsHandler.archive_dir, NewsHandler.web_dir = args.database, args.archives, args.web
    NewsHandler.refresh_hours = max(0, args.refresh_hours)
    server = ThreadingHTTPServer((args.host, args.port), NewsHandler)
    stop_event = threading.Event()

    def refresh_loop():
        interval = NewsHandler.refresh_hours * 3600
        first = True
        while interval > 0:
            if (not first or args.no_refresh_on_start) and stop_event.wait(interval):
                break
            first = False
            print("Scheduled refresh started")
            result = subprocess.run([sys.executable, "-m", "daily_news"], check=False)
            print(f"Scheduled refresh finished with exit code {result.returncode}")

    if NewsHandler.refresh_hours > 0:
        threading.Thread(target=refresh_loop, name="news-refresh", daemon=True).start()
    print(f"Signal Daily running at http://{args.host}:{args.port} (refresh every {NewsHandler.refresh_hours:g}h)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
