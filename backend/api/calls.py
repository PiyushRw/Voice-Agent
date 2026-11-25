import json
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field
from ..config import LIVE
from ..database import db, history, add_message, now
from ..agents.graph import turn, call_lock
from ..services.summarizer import finish
from .livekit import credentials
try:
    from ..api.appointments import _init_appointments  # ensure table exists
except Exception:
    pass

router = APIRouter(prefix="/calls")

class Message(BaseModel):
    text: str = Field(min_length=1,max_length=1500)

class Start(BaseModel):
    voice: bool = False

def lookup(call_id):
    with db() as con:
        row = con.execute("SELECT * FROM calls WHERE id=?", (call_id,)).fetchone()
    if not row:
        raise HTTPException(404,"Call not found.")
    return row

@router.post("")
def start(options: Start):
    call_id = uuid4().hex
    if options.voice and not LIVE:
        raise HTTPException(409,"Start the server in live mode to use the microphone.")
    connection = credentials(call_id) if options.voice else {}
    mode = "live" if options.voice else "demo"
    with db() as con:
        con.execute("INSERT INTO calls(id,started,mode) VALUES(?,?,?)",(call_id,now(),mode))
    if mode == "demo":
        add_message(call_id,"assistant","Hi there! I'm Maya from FlowCRM. How can I help you today?")
    return {"id":call_id,"mode":mode,**connection}

@router.post("/{call_id}/messages")
def message(call_id: str, payload: Message):
    with call_lock(call_id):
        row = lookup(call_id)
        if row["ended"]:
            raise HTTPException(409,"This call has already ended.")
        if not payload.text.strip():
            raise HTTPException(422,"Please enter a message.")
        mode = "live" if LIVE else row["mode"]
        result = turn(call_id,payload.text,mode)
        add_message(call_id,"assistant",result["reply"],result["language"])
    return {k:result[k] for k in ("reply","language","sources","sentiment","objections")
            if k in result} | {"appointment": result.get("appointment")}

def finalize(call_id):
    with call_lock(call_id):
        finish(call_id)

@router.post("/{call_id}/end")
def end(call_id: str, background: BackgroundTasks):
    row = lookup(call_id)
    if row["ended"]:
        return {"status":"already_ended"}
    background.add_task(finalize,call_id)
    return {"status":"finalizing"}

@router.get("")
def calls():
    with db() as con:
        return [dict(row) for row in con.execute("""SELECT calls.id,started,ended,mode,
            leads.score,leads.status,json_extract(leads.details,'$.name') AS name,call_analysis.sentiment,call_analysis.outcome
            FROM calls LEFT JOIN leads ON calls.id=leads.call_id
            LEFT JOIN call_analysis ON calls.id=call_analysis.call_id
            ORDER BY started DESC LIMIT 100""")]

@router.get("/{call_id}")
def detail(call_id: str):
    row = lookup(call_id)
    result = {k:row[k] for k in ("id","started","ended","mode")}
    with db() as con:
        for table, key in (("leads","lead"),("call_analysis","analysis")):
            item = con.execute(f"SELECT * FROM {table} WHERE call_id=?",(call_id,)).fetchone()
            result[key] = dict(item) if item else None
        appts = con.execute(
            "SELECT * FROM appointments WHERE call_id=? ORDER BY date,time",(call_id,)
        ).fetchall()
        result["appointments"] = [dict(a) for a in appts]
    if result["lead"]:
        result["lead"]["details"] = json.loads(result["lead"]["details"])
    if result["analysis"]:
        result["analysis"]["objections"] = json.loads(result["analysis"]["objections"])
    result["messages"] = history(call_id)
    return result
