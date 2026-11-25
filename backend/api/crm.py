"""CRM integration layer – exposes lead pipeline, contact management,
and a webhook-compatible export endpoint that mirrors common CRM APIs
(HubSpot-style field names so it's easy to wire to a real CRM later)."""
import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from ..database import db
from ..api.auth import authorized
from fastapi import Depends

router = APIRouter(prefix="/crm", dependencies=[Depends(authorized)])

# ── pipeline ─────────────────────────────────────────────────────────────────

@router.get("/pipeline")
def pipeline():
    """Full lead pipeline with enriched contact and call data."""
    with db() as con:
        rows = con.execute("""
            SELECT
                calls.id AS call_id,
                calls.started, calls.ended, calls.mode,
                leads.score, leads.status, leads.details,
                call_analysis.summary, call_analysis.sentiment,
                call_analysis.objections, call_analysis.outcome,
                call_analysis.next_action,
                (SELECT COUNT(*) FROM appointments WHERE appointments.call_id=calls.id AND appointments.status='confirmed') AS appointments
            FROM calls
            LEFT JOIN leads ON calls.id=leads.call_id
            LEFT JOIN call_analysis ON calls.id=call_analysis.call_id
            WHERE leads.call_id IS NOT NULL
            ORDER BY leads.score DESC, calls.started DESC
            LIMIT 200
        """).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["details"] = json.loads(d["details"]) if d["details"] else {}
        d["objections"] = json.loads(d["objections"]) if d["objections"] else []
        result.append(d)
    return result

@router.get("/contact/{call_id}")
def contact(call_id: str):
    """Full contact record for a lead (HubSpot-style fields)."""
    with db() as con:
        lead = con.execute("SELECT * FROM leads WHERE call_id=?", (call_id,)).fetchone()
        if not lead:
            raise HTTPException(404, "No lead found for this call")
        analysis = con.execute("SELECT * FROM call_analysis WHERE call_id=?", (call_id,)).fetchone()
        appts = con.execute(
            "SELECT * FROM appointments WHERE call_id=? ORDER BY date,time", (call_id,)
        ).fetchall()
    details = json.loads(lead["details"]) if lead["details"] else {}
    return {
        # HubSpot-style property names
        "firstname": details.get("name", ""),
        "company": details.get("company", ""),
        "phone": details.get("phone", ""),
        "budget": details.get("budget", ""),
        "need": details.get("need", ""),
        "authority": details.get("authority", ""),
        "timeline": details.get("timeline", ""),
        "hs_lead_status": lead["status"],
        "hs_lead_score": lead["score"],
        "summary": analysis["summary"] if analysis else "",
        "sentiment": analysis["sentiment"] if analysis else "neutral",
        "objections": json.loads(analysis["objections"]) if analysis else [],
        "next_action": analysis["next_action"] if analysis else "",
        "appointments": [dict(a) for a in appts],
        "call_id": call_id,
    }

@router.get("/export")
def export():
    """Export all qualified leads as a flat list (CSV-ready)."""
    with db() as con:
        rows = con.execute("""
            SELECT calls.id,calls.started,calls.ended,calls.mode,
                leads.score,leads.status,leads.details,
                call_analysis.summary,call_analysis.sentiment,
                call_analysis.objections,call_analysis.next_action
            FROM calls
            JOIN leads ON calls.id=leads.call_id
            JOIN call_analysis ON calls.id=call_analysis.call_id
            WHERE leads.score>=45
            ORDER BY leads.score DESC
        """).fetchall()
    out = []
    for r in rows:
        d = json.loads(r["details"]) if r["details"] else {}
        out.append({
            "call_id": r["id"], "started": r["started"], "ended": r["ended"], "mode": r["mode"],
            "name": d.get("name",""), "company": d.get("company",""),
            "budget": d.get("budget",""), "need": d.get("need",""),
            "authority": d.get("authority",""), "timeline": d.get("timeline",""),
            "score": r["score"], "status": r["status"],
            "summary": r["summary"], "sentiment": r["sentiment"],
            "objections": ", ".join(json.loads(r["objections"]) if r["objections"] else []),
            "next_action": r["next_action"],
        })
    return out

@router.get("/insights")
def insights():
    """Aggregated sales insights for dashboard."""
    with db() as con:
        totals = con.execute("""
            SELECT
                COUNT(*) AS total_calls,
                COUNT(leads.call_id) AS total_leads,
                SUM(CASE WHEN leads.score>=75 THEN 1 ELSE 0 END) AS hot,
                SUM(CASE WHEN leads.score>=45 AND leads.score<75 THEN 1 ELSE 0 END) AS warm,
                SUM(CASE WHEN leads.score<45 THEN 1 ELSE 0 END) AS cold,
                AVG(leads.score) AS avg_score
            FROM calls LEFT JOIN leads ON calls.id=leads.call_id
            WHERE calls.ended IS NOT NULL
        """).fetchone()
        appt_count = con.execute(
            "SELECT COUNT(*) AS n FROM appointments WHERE status='confirmed'"
        ).fetchone()["n"]
        upcoming = con.execute("""
            SELECT COUNT(*) AS n FROM appointments
            WHERE status='confirmed' AND date>=date('now')
        """).fetchone()["n"]
        avg_duration_row = con.execute("""
            SELECT AVG((julianday(ended)-julianday(started))*86400) AS avg_secs
            FROM calls WHERE ended IS NOT NULL
        """).fetchone()
    t = dict(totals)
    return {
        "total_calls": t["total_calls"] or 0,
        "total_leads": t["total_leads"] or 0,
        "hot": t["hot"] or 0,
        "warm": t["warm"] or 0,
        "cold": t["cold"] or 0,
        "avg_score": round(t["avg_score"] or 0, 1),
        "appointments_booked": appt_count,
        "appointments_upcoming": upcoming,
        "avg_call_duration_secs": round(avg_duration_row["avg_secs"] or 0),
    }
