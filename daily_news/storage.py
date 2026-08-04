"""SQLite persistence and monthly, loss-safe archive rotation."""

import gzip
import json
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS reports (
    report_date TEXT PRIMARY KEY,
    generated_at TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    item_count INTEGER NOT NULL,
    market_count INTEGER NOT NULL,
    warning_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_reports_date ON reports(report_date DESC);
CREATE TABLE IF NOT EXISTS archive_log (
    month TEXT PRIMARY KEY,
    file_name TEXT NOT NULL,
    report_count INTEGER NOT NULL,
    archived_at TEXT NOT NULL,
    sha256 TEXT NOT NULL
);
"""


def connect(database: Path) -> sqlite3.Connection:
    database.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(database, timeout=30)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA foreign_keys=ON")
    connection.executescript(SCHEMA)
    return connection


def save_report(database: Path, payload: dict[str, Any]) -> None:
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    with closing(connect(database)) as connection:
        connection.execute(
            """INSERT INTO reports(report_date, generated_at, payload_json, item_count, market_count, warning_count)
               VALUES(?,?,?,?,?,?)
               ON CONFLICT(report_date) DO UPDATE SET generated_at=excluded.generated_at,
               payload_json=excluded.payload_json, item_count=excluded.item_count,
               market_count=excluded.market_count, warning_count=excluded.warning_count,
               updated_at=CURRENT_TIMESTAMP""",
            (payload["date"], payload["generated_at"], encoded, len(payload.get("items", [])),
             len(payload.get("markets", [])), len(payload.get("warnings", []))),
        )
        connection.commit()


def database_dates(database: Path) -> list[str]:
    with closing(connect(database)) as connection:
        return [row[0] for row in connection.execute("SELECT report_date FROM reports ORDER BY report_date DESC")]


def get_database_report(database: Path, report_date: str) -> dict[str, Any] | None:
    with closing(connect(database)) as connection:
        row = connection.execute("SELECT payload_json FROM reports WHERE report_date=?", (report_date,)).fetchone()
    return json.loads(row[0]) if row else None


def _archive_payload(month: str, rows: list[sqlite3.Row]) -> dict[str, Any]:
    reports = [json.loads(row["payload_json"]) for row in rows]
    return {
        "schema_version": 1,
        "month": month,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "report_count": len(reports),
        "dates": [report["date"] for report in reports],
        "reports": reports,
    }


def archive_month(database: Path, archive_dir: Path, month: str) -> dict[str, Any]:
    """Archive YYYY-MM atomically; DB rows are deleted only after file verification."""
    import hashlib

    if len(month) != 7 or month[4] != "-":
        raise ValueError("month must use YYYY-MM")
    archive_dir.mkdir(parents=True, exist_ok=True)
    destination = archive_dir / f"{month}.json.gz"
    temporary = archive_dir / f".{month}.{os.getpid()}.tmp"
    with closing(connect(database)) as connection:
        rows = connection.execute(
            "SELECT report_date, payload_json FROM reports WHERE substr(report_date,1,7)=? ORDER BY report_date", (month,)
        ).fetchall()
        if not rows:
            return {"month": month, "reports": 0, "status": "empty"}
        payload = _archive_payload(month, rows)
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        with gzip.open(temporary, "wb", compresslevel=9) as stream:
            stream.write(raw)
        with gzip.open(temporary, "rb") as stream:
            verified = json.loads(stream.read().decode("utf-8"))
        expected_dates = [row["report_date"] for row in rows]
        if verified.get("dates") != expected_dates or verified.get("report_count") != len(rows):
            temporary.unlink(missing_ok=True)
            raise RuntimeError("archive verification failed; database was not modified")
        os.replace(temporary, destination)
        digest = hashlib.sha256(destination.read_bytes()).hexdigest()
        with connection:
            connection.execute(
                "INSERT OR REPLACE INTO archive_log(month,file_name,report_count,archived_at,sha256) VALUES(?,?,?,?,?)",
                (month, destination.name, len(rows), datetime.now(timezone.utc).isoformat(), digest),
            )
            connection.execute("DELETE FROM reports WHERE substr(report_date,1,7)=?", (month,))
    return {"month": month, "reports": len(rows), "status": "archived", "file": str(destination)}


def archive_completed_months(database: Path, archive_dir: Path, current_date: date) -> list[dict[str, Any]]:
    current_month = current_date.strftime("%Y-%m")
    with closing(connect(database)) as connection:
        months = [row[0] for row in connection.execute(
            "SELECT DISTINCT substr(report_date,1,7) FROM reports WHERE substr(report_date,1,7) < ? ORDER BY 1", (current_month,)
        )]
    return [archive_month(database, archive_dir, month) for month in months]


def archive_dates(archive_dir: Path) -> list[str]:
    dates: list[str] = []
    for path in sorted(archive_dir.glob("????-??.json.gz"), reverse=True) if archive_dir.exists() else []:
        try:
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                dates.extend(json.load(stream).get("dates", []))
        except (OSError, ValueError):
            continue
    return sorted(set(dates), reverse=True)


def get_archived_report(archive_dir: Path, report_date: str) -> dict[str, Any] | None:
    path = archive_dir / f"{report_date[:7]}.json.gz"
    if not path.exists():
        return None
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        payload = json.load(stream)
    return next((report for report in payload.get("reports", []) if report.get("date") == report_date), None)


def list_archives(database: Path, archive_dir: Path) -> list[dict[str, Any]]:
    with closing(connect(database)) as connection:
        rows = connection.execute("SELECT month,file_name,report_count,archived_at,sha256 FROM archive_log ORDER BY month DESC").fetchall()
    logged = {row["month"]: dict(row) for row in rows}
    for path in archive_dir.glob("????-??.json.gz") if archive_dir.exists() else []:
        logged.setdefault(path.name[:7], {"month": path.name[:7], "file_name": path.name, "report_count": None, "archived_at": None, "sha256": None})
    return sorted(logged.values(), key=lambda row: row["month"], reverse=True)
