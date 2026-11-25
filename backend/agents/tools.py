"""Agent-callable tools injected into the LangGraph sales node.

These are called from nodes.sales() when the LLM or rule-engine detects
a booking intent or CRM-update intent so that the agent can actually
complete the action mid-conversation and report confirmation back.
"""
import json
from datetime import datetime, timezone, timedelta
from ..database import db, now


# ── appointment booking ───────────────────────────────────────────────────────

def book_appointment(call_id: str, name: str, date_str: str, time_str: str,
                     email: str = "", phone: str = "", notes: str = "") -> dict:
    """
    Book a demo/discovery appointment for a lead.
    Returns {"ok": True, "id": <int>} or {"ok": False, "reason": <str>}.
    """
    from ..api.appointments import available_slots, date_parse
    try:
        d = date_parse(date_str)
    except ValueError:
        return {"ok": False, "reason": "Invalid date format, need YYYY-MM-DD"}
    with db() as con:
        existing = con.execute(
            "SELECT id, date, time FROM appointments WHERE call_id=? AND status='confirmed' ORDER BY id DESC LIMIT 1",
            (call_id,)
        ).fetchone()
    if time_str not in available_slots(d) and not (existing and existing["date"] == date_str and existing["time"] == time_str):
        slots = available_slots(d)
        if not slots:
            return {"ok": False, "reason": f"No slots available on {date_str}"}
        time_str = slots[0]        # auto-pick first open slot

    with db() as con:
        if existing:
            con.execute(
                "UPDATE appointments SET name=?, email=?, phone=?, date=?, time=?, notes=COALESCE(NULLIF(?,''),notes) WHERE id=?",
                (name, email, phone, date_str, time_str, notes, existing["id"])
            )
            appt_id = existing["id"]
        else:
            con.execute(
                "INSERT INTO appointments(call_id,name,email,phone,date,time,notes,created) VALUES(?,?,?,?,?,?,?,?)",
                (call_id, name, email, phone, date_str, time_str, notes, now())
            )
            appt_id = con.execute("SELECT last_insert_rowid() AS id").fetchone()["id"]
    from ..tools.qualification import qualify
    qualify(call_id, {})   # refresh lead score to include the booked appointment
    return {"ok": True, "id": appt_id, "date": date_str, "time": time_str}


def next_available(days_ahead: int = 7) -> list[dict]:
    """Return up to 3 upcoming working days with their first open slot."""
    from ..api.appointments import available_slots
    result = []
    d = (datetime.now(timezone.utc) + timedelta(days=1)).date()
    checked = 0
    while len(result) < 3 and checked < days_ahead:
        slots = available_slots(d)
        if slots:
            result.append({"date": d.isoformat(), "time": slots[0]})
        from datetime import date, timedelta as td
        d = d + td(days=1)
        checked += 1
    return result


# ── CRM helpers ───────────────────────────────────────────────────────────────

def update_lead_note(call_id: str, note: str) -> bool:
    """Append a CRM note to the call's lead details."""
    with db() as con:
        row = con.execute("SELECT details FROM leads WHERE call_id=?", (call_id,)).fetchone()
        if not row:
            return False
        details = json.loads(row["details"])
        notes = details.get("notes", [])
        if isinstance(notes, str):
            notes = [notes]
        notes.append(note[:300])
        details["notes"] = notes[-5:]          # keep last 5 notes
        con.execute("UPDATE leads SET details=? WHERE call_id=?",
                    (json.dumps(details, ensure_ascii=False), call_id))
    return True


def get_lead_summary(call_id: str) -> dict:
    """Return current lead details + appointments for the agent to reference."""
    with db() as con:
        lead = con.execute("SELECT details,score,status FROM leads WHERE call_id=?",
                           (call_id,)).fetchone()
        appts = con.execute(
            "SELECT date,time,status FROM appointments WHERE call_id=? ORDER BY date,time",
            (call_id,)
        ).fetchall()
    if not lead:
        return {}
    details = json.loads(lead["details"]) if lead["details"] else {}
    return {**details, "score": lead["score"], "status": lead["status"],
            "appointments": [dict(a) for a in appts]}
