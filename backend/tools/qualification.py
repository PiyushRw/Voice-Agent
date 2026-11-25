import json
from ..database import db

WEIGHTS = {"budget": 25, "authority": 20, "need": 25, "timeline": 20}

def qualify(call_id, result):
    with db() as con:
        row = con.execute("SELECT details FROM leads WHERE call_id=?", (call_id,)).fetchone()
        details = json.loads(row["details"]) if row else {}
        for key in (*WEIGHTS, "name", "company", "email", "phone"):
            value = result.get(key)
            if isinstance(value, (str, int)) and not isinstance(value, bool) and str(value).strip():
                if str(value).strip().lower() not in {"unknown","none","null","n/a","unspecified"}:
                    details[key] = str(value).strip()[:300]

        score = sum(points for key, points in WEIGHTS.items() if details.get(key))

        # Engagement & buying-intent signals
        contact_fields = sum(1 for k in ("company", "email", "phone") if details.get(k))
        if contact_fields >= 2:
            score += 15
        elif contact_fields == 1:
            score += 5

        has_appt = con.execute(
            "SELECT 1 FROM appointments WHERE call_id=? AND status='confirmed' LIMIT 1",
            (call_id,),
        ).fetchone()
        if has_appt:
            score += 35

        score = min(100, score)
        status = "Hot" if score >= 75 else "Warm" if score >= 45 else "Cold"
        con.execute("INSERT OR REPLACE INTO leads VALUES(?,?,?,?)", (call_id, json.dumps(details), score, status))
        if any(k in result for k in ("name", "email", "phone")):
            con.execute(
                "UPDATE appointments SET name=?, email=?, phone=? WHERE call_id=? AND status='confirmed'",
                (details.get("name", "Customer"), details.get("email", ""), details.get("phone", ""), call_id),
            )
    return details
