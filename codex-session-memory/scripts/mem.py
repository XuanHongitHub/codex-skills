#!/usr/bin/env python3
import argparse
import datetime as dt
import os
import sqlite3
import subprocess
from pathlib import Path
from typing import Iterable, List


DEFAULT_DB = Path(".agents/skills/codex-session-memory/data/memory.db")


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def ensure_db(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS observations (
          id INTEGER PRIMARY KEY AUTOINCREMENT,
          created_at TEXT NOT NULL,
          project TEXT NOT NULL,
          kind TEXT NOT NULL,
          summary TEXT NOT NULL,
          details TEXT,
          tags TEXT,
          files TEXT
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_observations_created_at ON observations(created_at)"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_observations_kind ON observations(kind)")
    conn.commit()
    return conn


def normalize_csv(value: str | None) -> str:
    if not value:
        return ""
    parts = [p.strip() for p in value.split(",")]
    return ",".join([p for p in parts if p])


def run_capture(command: List[str]) -> str:
    try:
        out = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            check=False,
            timeout=3,
        )
        return out.stdout.strip()
    except Exception:
        return ""


def detect_project_name() -> str:
    git_root = run_capture(["git", "rev-parse", "--show-toplevel"])
    if git_root:
        return Path(git_root).name
    return Path.cwd().name


def add_observation(
    conn: sqlite3.Connection,
    *,
    project: str,
    kind: str,
    summary: str,
    details: str,
    tags: str,
    files: str,
) -> int:
    cursor = conn.execute(
        """
        INSERT INTO observations(created_at, project, kind, summary, details, tags, files)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (utc_now(), project, kind, summary.strip(), details.strip(), tags, files),
    )
    conn.commit()
    return int(cursor.lastrowid)


def print_rows(rows: Iterable[sqlite3.Row], full: bool = False) -> None:
    for row in rows:
        if full:
            print(f"[{row['id']}] {row['created_at']} {row['kind']} {row['project']}")
            print(f"summary: {row['summary']}")
            if row["details"]:
                print(f"details: {row['details']}")
            if row["tags"]:
                print(f"tags: {row['tags']}")
            if row["files"]:
                print(f"files: {row['files']}")
            print("")
            continue
        summary = row["summary"][:120].replace("\n", " ").strip()
        print(
            f"[{row['id']}] {row['created_at']} kind={row['kind']} "
            f"tags={row['tags'] or '-'} :: {summary}"
        )


def cmd_init(args: argparse.Namespace) -> int:
    conn = ensure_db(Path(args.db))
    conn.close()
    print(f"Initialized memory database at {Path(args.db)}")
    return 0


def cmd_add(args: argparse.Namespace) -> int:
    conn = ensure_db(Path(args.db))
    obs_id = add_observation(
        conn,
        project=args.project or detect_project_name(),
        kind=args.type,
        summary=args.summary,
        details=args.details or "",
        tags=normalize_csv(args.tags),
        files=normalize_csv(args.files),
    )
    conn.close()
    print(f"Saved observation #{obs_id}")
    return 0


def cmd_checkpoint(args: argparse.Namespace) -> int:
    branch = run_capture(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    status = run_capture(["git", "status", "--short"])
    diff_names = run_capture(["git", "diff", "--name-only"])
    details_lines = []
    if args.why:
        details_lines.append(f"why: {args.why}")
    if branch:
        details_lines.append(f"branch: {branch}")
    if status:
        details_lines.append("status:\n" + status)
    if diff_names:
        details_lines.append("changed_files:\n" + diff_names)
    details = "\n\n".join(details_lines)

    conn = ensure_db(Path(args.db))
    obs_id = add_observation(
        conn,
        project=args.project or detect_project_name(),
        kind="checkpoint",
        summary=args.summary,
        details=details,
        tags=normalize_csv(args.tags),
        files=normalize_csv(diff_names.replace("\n", ",")),
    )
    conn.close()
    print(f"Saved checkpoint #{obs_id}")
    return 0


def cmd_search(args: argparse.Namespace) -> int:
    conn = ensure_db(Path(args.db))
    conn.row_factory = sqlite3.Row
    terms = [t.strip().lower() for t in args.query.split() if t.strip()]
    if not terms:
        print("Empty query")
        conn.close()
        return 1

    where_parts = []
    params: List[str | int] = []
    for term in terms:
        like = f"%{term}%"
        where_parts.append(
            "("
            "lower(summary) LIKE ? OR "
            "lower(details) LIKE ? OR "
            "lower(tags) LIKE ? OR "
            "lower(kind) LIKE ? OR "
            "lower(project) LIKE ?"
            ")"
        )
        params.extend([like, like, like, like, like])
    params.append(args.limit)

    rows = conn.execute(
        f"""
        SELECT id, created_at, project, kind, summary, tags, files
        FROM observations
        WHERE {' AND '.join(where_parts)}
        ORDER BY id DESC
        LIMIT ?
        """,
        params,
    ).fetchall()
    conn.close()
    print_rows(rows, full=False)
    return 0


def cmd_timeline(args: argparse.Namespace) -> int:
    conn = ensure_db(Path(args.db))
    conn.row_factory = sqlite3.Row
    center = conn.execute(
        "SELECT id FROM observations WHERE id = ? LIMIT 1", (args.id,)
    ).fetchone()
    if not center:
        print(f"Observation #{args.id} not found")
        conn.close()
        return 1
    min_id = max(1, args.id - args.window)
    max_id = args.id + args.window
    rows = conn.execute(
        """
        SELECT id, created_at, project, kind, summary, tags, files
        FROM observations
        WHERE id BETWEEN ? AND ?
        ORDER BY id ASC
        """,
        (min_id, max_id),
    ).fetchall()
    conn.close()
    print_rows(rows, full=False)
    return 0


def parse_ids(value: str) -> List[int]:
    ids: List[int] = []
    for raw in value.split(","):
        raw = raw.strip()
        if not raw:
            continue
        ids.append(int(raw))
    if not ids:
        raise ValueError("At least one ID is required")
    return ids


def cmd_get(args: argparse.Namespace) -> int:
    ids = parse_ids(args.ids)
    placeholders = ",".join(["?"] * len(ids))
    conn = ensure_db(Path(args.db))
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"""
        SELECT id, created_at, project, kind, summary, details, tags, files
        FROM observations
        WHERE id IN ({placeholders})
        ORDER BY id ASC
        """,
        ids,
    ).fetchall()
    conn.close()
    print_rows(rows, full=True)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Codex local memory helper")
    parser.add_argument("--db", default=str(DEFAULT_DB), help="Path to sqlite db")

    sub = parser.add_subparsers(dest="cmd", required=True)

    init_p = sub.add_parser("init", help="Initialize database")
    init_p.set_defaults(func=cmd_init)

    add_p = sub.add_parser("add", help="Add a memory observation")
    add_p.add_argument("--type", default="note", help="Observation type")
    add_p.add_argument("--summary", required=True, help="Short summary")
    add_p.add_argument("--details", default="", help="Full details")
    add_p.add_argument("--tags", default="", help="Comma-separated tags")
    add_p.add_argument("--files", default="", help="Comma-separated files")
    add_p.add_argument("--project", default="", help="Project name override")
    add_p.set_defaults(func=cmd_add)

    cp_p = sub.add_parser("checkpoint", help="Capture checkpoint from git state")
    cp_p.add_argument("--summary", required=True, help="Checkpoint summary")
    cp_p.add_argument("--why", default="", help="Why this checkpoint matters")
    cp_p.add_argument("--tags", default="checkpoint", help="Comma-separated tags")
    cp_p.add_argument("--project", default="", help="Project name override")
    cp_p.set_defaults(func=cmd_checkpoint)

    search_p = sub.add_parser("search", help="Search compact index")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--limit", type=int, default=10, help="Max results")
    search_p.set_defaults(func=cmd_search)

    tl_p = sub.add_parser("timeline", help="Show nearby observations by ID")
    tl_p.add_argument("--id", type=int, required=True, help="Center observation id")
    tl_p.add_argument("--window", type=int, default=2, help="IDs before/after center")
    tl_p.set_defaults(func=cmd_timeline)

    get_p = sub.add_parser("get", help="Get full details by IDs")
    get_p.add_argument("--ids", required=True, help="Comma-separated observation IDs")
    get_p.set_defaults(func=cmd_get)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
