from collections import Counter
import json
from fastapi import APIRouter
from ..database import db

router = APIRouter()

@router.get("/analytics")
def analytics():
    with db() as con:
        rows = con.execute("""SELECT calls.mode, leads.status, call_analysis.sentiment,
            call_analysis.objections, call_analysis.outcome
            FROM calls JOIN call_analysis ON calls.id=call_analysis.call_id
            LEFT JOIN leads ON calls.id=leads.call_id""").fetchall()
    groups = {}
    for mode in ("demo","live"):
        items = [r for r in rows if r["mode"] == mode]
        leads = Counter(r["status"] for r in items if r["status"])
        groups[mode] = {"calls":len(items),"qualified":leads["Hot"] + leads["Warm"],
                        "rate":round(100 * (leads["Hot"] + leads["Warm"]) / len(items),1) if items else 0,
                        "leads":dict(leads),"sentiment":dict(Counter(r["sentiment"] for r in items)),
                        "objections":dict(Counter(o for r in items for o in json.loads(r["objections"])))}
    return groups
