from __future__ import annotations
import os, sqlite3, threading, time
from pathlib import Path
from typing import Any
DB_PATH = Path(os.getenv("JOB_DB", "jobs/karaokeforge.db")); DB_PATH.parent.mkdir(parents=True, exist_ok=True); LOCK = threading.RLock()
SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY, filename TEXT NOT NULL, status TEXT NOT NULL, progress INTEGER NOT NULL DEFAULT 0, message TEXT NOT NULL DEFAULT '', error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL);
CREATE INDEX IF NOT EXISTS idx_jobs_queue ON jobs(status, created_at);
"""
def _db() -> sqlite3.Connection:
    db=sqlite3.connect(DB_PATH,timeout=30,check_same_thread=False); db.row_factory=sqlite3.Row; db.executescript(SCHEMA); return db
def create_job(job_id: str, filename: str) -> None:
    now=time.time()
    with LOCK, _db() as db: db.execute("INSERT INTO jobs(id,filename,status,progress,message,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",(job_id,filename,"queued",0,"Waiting to start",now,now)); db.commit()
def update_job(job_id: str, *, status: str, progress: int, message: str, error: str|None=None) -> None:
    with LOCK, _db() as db: db.execute("UPDATE jobs SET status=?,progress=?,message=?,error=?,updated_at=? WHERE id=?",(status,progress,message,error,time.time(),job_id)); db.commit()
def get_job(job_id: str) -> dict[str,Any]|None:
    with LOCK, _db() as db: row=db.execute("SELECT * FROM jobs WHERE id=?",(job_id,)).fetchone()
    return dict(row) if row else None
def queued_jobs()->list[str]:
    with LOCK, _db() as db: rows=db.execute("SELECT id FROM jobs WHERE status='queued' ORDER BY created_at").fetchall()
    return [str(r[0]) for r in rows]
def reset_running_jobs()->None:
    with LOCK, _db() as db: db.execute("UPDATE jobs SET status='queued',progress=0,message='Waiting to resume',error=NULL,updated_at=? WHERE status='running'",(time.time(),)); db.commit()
def count_jobs()->int:
    with LOCK, _db() as db: row=db.execute("SELECT COUNT(*) FROM jobs").fetchone()
    return int(row[0])
