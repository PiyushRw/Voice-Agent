"""Appointment booking API – slots are stored in SQLite, mirroring a real CRM calendar."""
import json
from datetime import date, datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..database import db, now
from ..api.auth import authorized
from fastapi import Depends

router = APIRouter(prefix="/appointments", dependencies=[Depends(authorized)])

# ── helpers ──────────────────────────────────────────────────────────────────

def _init_appointments(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS appointments(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        call_id TEXT REFERENCES calls(id),
        name TEXT, email TEXT, phone TEXT,
        date TEXT, time TEXT, notes TEXT,
        status TEXT DEFAULT 'confirmed',
        created TEXT
    );
    CREATE INDEX IF NOT EXISTS appt_call ON appointments(call_id);
    """)

def _ensure_table():
    with db() as con:
        _init_appointments(con)

_ensure_table()

# ── slot generation ───────────────────────────────────────────────────────────

def available_slots(target_date: date) -> list[str]:
    """Return 30-min slots 9 AM–6 PM on working days, minus already booked ones."""
    if target_date.weekday() >= 5:            # Sat/Sun → no slots
        return []
    with db() as con:
        booked = {r["time"] for r in con.execute(
            "SELECT time FROM appointments WHERE date=? AND status!='cancelled'",
            (target_date.isoformat(),)
        )}
    slots = []
    for h in range(9, 18):
        for m in (0, 30):
            t = f"{h:02d}:{m:02d}"
            if t not in booked:
                slots.append(t)
    return slots

# ── models ───────────────────────────────────────────────────────────────────

class BookRequest(BaseModel):
    call_id: str = Field(min_length=32, max_length=32)
    name: str    = Field(min_length=1, max_length=120)
    email: str   = Field(default="", max_length=200)
    phone: str   = Field(default="", max_length=40)
    date: str    = Field(description="YYYY-MM-DD")
    time: str    = Field(description="HH:MM")
    notes: str   = Field(default="", max_length=500)

class CancelRequest(BaseModel):
    appointment_id: int

# ── routes ───────────────────────────────────────────────────────────────────

@router.get("/slots")
def slots(date: str):
    """Return available 30-minute slots for a given date (YYYY-MM-DD)."""
    try:
        d = date_parse(date)
    except ValueError:
        raise HTTPException(422, "Invalid date format, use YYYY-MM-DD")
    return {"date": date, "slots": available_slots(d)}

@router.get("/next-slots")
def next_slots():
    """Return next 5 working days with their available slot counts."""
    result = []
    d = datetime.now(timezone.utc).date() + timedelta(days=1)
    while len(result) < 5:
        s = available_slots(d)
        if s:
            result.append({"date": d.isoformat(), "available": len(s), "first_slot": s[0]})
        d += timedelta(days=1)
    return result

@router.post("")
def book(payload: BookRequest):
    """Book a slot. Returns the new appointment id."""
    try:
        d = date_parse(payload.date)
    except ValueError:
        raise HTTPException(422, "Invalid date format")
    if payload.time not in available_slots(d):
        raise HTTPException(409, "That slot is no longer available. Please choose another.")
    with db() as con:
        con.execute(
            "INSERT INTO appointments(call_id,name,email,phone,date,time,notes,created) VALUES(?,?,?,?,?,?,?,?)",
            (payload.call_id, payload.name, payload.email, payload.phone,
             payload.date, payload.time, payload.notes, now())
        )
        appt_id = con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    return {"id": appt_id, "status": "confirmed", "date": payload.date, "time": payload.time}

@router.get("")
def list_appointments():
    """List all upcoming confirmed appointments."""
    today = datetime.now(timezone.utc).date().isoformat()
    with db() as con:
        rows = con.execute(
            "SELECT * FROM appointments WHERE date>=? ORDER BY date,time LIMIT 200", (today,)
        ).fetchall()
    return [dict(r) for r in rows]

@router.get("/{call_id}/call")
def call_appointments(call_id: str):
    """Appointments linked to a specific call."""
    with db() as con:
        rows = con.execute(
            "SELECT * FROM appointments WHERE call_id=? ORDER BY date,time", (call_id,)
        ).fetchall()
    return [dict(r) for r in rows]

@router.post("/{appointment_id}/cancel")
def cancel(appointment_id: int):
    with db() as con:
        row = con.execute("SELECT id FROM appointments WHERE id=?", (appointment_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Appointment not found")
        con.execute("UPDATE appointments SET status='cancelled' WHERE id=?", (appointment_id,))
    return {"status": "cancelled"}

def date_parse(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()
