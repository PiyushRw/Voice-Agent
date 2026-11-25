import json
import re
from datetime import datetime, timezone, timedelta
from ..database import add_message, db, history
from ..rag.retrieval import search
from ..services.llm import ask
from ..tools.qualification import qualify
from ..agents.tools import book_appointment, next_available, get_lead_summary


def language(text):
    return "hi" if re.search(r"[\u0900-\u097f\u0600-\u06ff]|\b(kya|hai|chahiye|mera|kitna|haan|hindi|mein|baat)\b",text,re.I) else "en"

def local_interpret(text):
    result = {"language": language(text)}
    patterns = {
        "name":r"(?:my name is|मेरा नाम)\s+([^,.]+)",
        "company":r"(?:company is|company:)\s*([^,.]+)",
        "budget":r"(?:budget(?: is|:)?|बजट)\s*[₹ ]*(\d[\d,]*\d|\d)",
        "need":r"(?:i need|we need|looking for|चाहिए:)\s+([^,.]+)",
        "authority":r"\b(i (?:am the decision maker|make the decision|approve purchases)|decision maker)\b",
        "timeline":r"\b(within \d+ (?:days|weeks)|this month|next month|as soon as possible)\b",
    }
    for key,pattern in patterns.items():
        match = re.search(pattern,text,re.I)
        if match:
            result[key] = match[1]
    result["sentiment"] = "negative" if re.search(r"expensive|frustrated|महंगा",text,re.I) else "positive" if re.search(r"great|love|excellent|बढ़िया",text,re.I) else "neutral"
    result["objections"] = ["Pricing"] if re.search(r"expensive|महंगा",text,re.I) else []
    return result

def interpret(state):
    text = state["message"]
    call_id = state["call_id"]
    with db() as con:
        lead = con.execute("SELECT details FROM leads WHERE call_id=?", (call_id,)).fetchone()
    previous = [{k: item[k] for k in ("role","content","interrupted")}
                for item in history(call_id)[-14:]]
    quick = local_interpret(text)
    result, snippets = quick, []
    if state["mode"] == "live" or re.search(r"\?|price|pricing|plans|cost|features|trial|cancel|csv|कीमत|प्लान|kitna|what|how|does|can",text,re.I):
        snippets = search(text)
    if state["mode"] == "live":
        result = ask({
            "today": datetime.now(timezone.utc).date().isoformat(),
            "available_slots": next_available(days_ahead=7),
            "customer": text,
            "history": previous,
            "knowledge": snippets,
            "known_lead": json.loads(lead["details"]) if lead else {},
        }) or quick
    lang = result.get("language")
    if lang not in {"en","hi"}:
        lang = quick["language"]
    add_message(call_id, "user", text, lang)
    objections = result.get("objections", [])
    objections = [x[:90] for x in objections if isinstance(x,str)][:6] if isinstance(objections,list) else []
    sentiment = result.get("sentiment")
    if sentiment not in ("positive","negative","neutral"):
        sentiment = "neutral"
    return {"interpretation":result,"language":lang,"context":snippets,
            "sources":[row["source"] for row in snippets],
            "sentiment":sentiment,"objections":objections}

BOOK_PATTERN = re.compile(
    r"\b(book|schedule|set up|arrange|fix|confirm|demo|appointment|meeting|call back|slot|available)\b|बुक|डेमो|मीटिंग",
    re.I
)

def _today_plus(days=1):
    return (datetime.now(timezone.utc) + timedelta(days=days)).date().isoformat()

def _parse_date(text, result):
    llm_date = result.get("appointment_date")
    if isinstance(llm_date, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", llm_date.strip()):
        return llm_date.strip()
    date_m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", text)
    if date_m:
        return date_m.group(1)
    if re.search(r"\btomorrow\b|कल", text, re.I):
        return _today_plus(1)
    if re.search(r"\bnext week\b|अगले हफ्ते", text, re.I):
        return _today_plus(7)
    return None

DATE_OR_CONFIRM = re.compile(
    r"(\d{4}-\d{2}-\d{2}|\b(tomorrow|today|next week|mon(day)?|tue(sday)?|wed(nesday)?|thu(rsday)?|fri(day)?|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\b|\b\d{1,2}:\d{2}\b|\b\d{1,2}\s*(?:am|pm)\b"
    r"|कल|परसों|आज|सोमवार|मंगलवार|बुधवार|गुरुवार|शुक्रवार|बजे|नवंबर|दिसंबर|\b(yes|yeah|sure|ok|okay|confirm)\b|हाँ|ठीक है)",
    re.I,
)

def sales(state):
    call_id, text, mode = (state[k] for k in ("call_id","message","mode"))
    if re.search(r"[\uac00-\ud7af\u4e00-\u9fff\u3040-\u30ff]", text):
        return {"reply": "माफ़ कीजिए, आपकी आवाज़ स्पष्ट नहीं आई। कृपया हिंदी या अंग्रेज़ी में दोबारा कहें।", "appointment": None}
    result = state["interpretation"]
    details = qualify(call_id, result)
    hi = state["language"] == "hi"
    appointment = state.get("appointment")

    def say(en, hindi=""):
        return {"reply": (hindi or en) if hi else en, "appointment": appointment}

    # ── recall ────────────────────────────────────────────────────────────────
    if re.search(r"\b(remember|my budget|my requirements|my name)\b|याद", text, re.I) \
            and details and (text.endswith("?") or "remember" in text.lower()):
        summary = get_lead_summary(call_id)
        parts = [f"{k}: {v}" for k, v in summary.items()
                 if k not in ("score","status","appointments","notes") and v]
        body = ", ".join(parts) or "Nothing captured yet."
        appt_list = summary.get("appointments", [])
        if appt_list:
            a = appt_list[-1]
            body += f". Demo booked for {a['date']} at {a['time']}."
        return say(f"Here's what I have so far: {body}",
                   f"अब तक की जानकारी: {body}")

    # ── booking intent ────────────────────────────────────────────────────────
    target_date = _parse_date(text, result)
    confirmed_by_llm = bool(result.get("appointment_confirmed")) and bool(DATE_OR_CONFIRM.search(text))
    should_book = bool(target_date and (confirmed_by_llm or mode == "demo"))
    wants_booking = bool(result.get("appointment_requested") or should_book or BOOK_PATTERN.search(text))
    if wants_booking:
        name = details.get("name", "Customer")
        email = details.get("email", "")
        phone = details.get("phone", "")
        target_time = result.get("appointment_time") or "10:00"
        if not re.match(r"^\d{2}:\d{2}$", str(target_time)):
            target_time = "10:00"

        if should_book:
            booked = book_appointment(call_id, name, target_date, target_time, email=email, phone=phone)
            if booked.get("ok"):
                appointment = {"id": booked["id"], "date": booked["date"], "time": booked["time"]}
                llm_reply = result.get("reply")
                contradicts = isinstance(llm_reply, str) and re.search(
                    r"(not|isn't|aren't|unavailable|उपलब्ध नहीं)", llm_reply, re.I
                )
                time_mismatch = booked["time"] != target_time
                if isinstance(llm_reply, str) and llm_reply.strip() and not contradicts and not time_mismatch:
                    return {"reply": llm_reply.strip()[:700], "appointment": appointment}
                return say(
                    f"Great, {name}! I've booked a demo for {booked['date']} at {booked['time']}. "
                    f"Our team will send a calendar invite shortly.",
                    f"बढ़िया, {name}! {booked['date']} को {booked['time']} बजे डेमो बुक हो गया है।"
                )
            elif not (isinstance(result.get("reply"), str) and result["reply"].strip()):
                slots = next_available()
                if slots:
                    s = slots[0]
                    return say(
                        f"That slot isn't available. The next open slot is {s['date']} at {s['time']}. Shall I book that?",
                        f"वह स्लॉट उपलब्ध नहीं है। अगला खुला स्लॉट {s['date']} को {s['time']} बजे है।"
                    )
        elif not (isinstance(result.get("reply"), str) and result["reply"].strip()):
            slots = next_available(days_ahead=10)
            if slots:
                options = "; ".join(f"{s['date']} at {s['time']}" for s in slots[:3])
                return say(
                    f"I'd love to schedule a demo! Next available slots: {options}. Which works for you?",
                    f"डेमो बुक करते हैं! अगले उपलब्ध समय: {options}। कौन सा ठीक रहेगा?"
                )

    # ── LLM reply (live) or RAG (demo) ───────────────────────────────────────
    reply = result.get("reply")
    if isinstance(reply, str) and reply.strip():
        return {"reply": reply.strip()[:700], "appointment": appointment}
    if state["context"]:
        chunk = state["context"][0]["text"]
        paragraphs = (chunk.partition("\n\n")[2] or chunk).split("\n\n")
        preferred = [part for part in paragraphs if language(part) == state["language"]]
        return {"reply": (preferred or paragraphs)[0][:500], "appointment": appointment}

    # ── objection handling ────────────────────────────────────────────────────
    if "Pricing" in state["objections"]:
        return say(
            "I understand the price is a concern. We also offer a free 14-day trial — no credit card needed. Want me to book a guided demo so you can see the value firsthand?",
            "कीमत की चिंता समझ में आती है। हम 14 दिनों का मुफ़्त ट्रायल भी देते हैं। क्या डेमो बुक करें?"
        )

    # ── BANT-guided questions ─────────────────────────────────────────────────
    if "need" not in details:
        return say("What would you like your sales team to manage with a CRM?",
                   "आपकी सेल्स टीम CRM से क्या संभालना चाहती है?")
    if "budget" not in details:
        return say("Do you have a rough monthly budget in mind for this?",
                   "क्या आपके मन में मासिक बजट का कोई अनुमान है?")
    if "timeline" not in details:
        return say("What's your timeline for getting this up and running?",
                   "आप इसे कब तक शुरू करना चाहते हैं?")
    if "authority" not in details:
        return say("Who else is involved in the buying decision for your team?",
                   "खरीदारी के फैसले में और कौन शामिल है?")

    # ── all BANT captured → push to book ─────────────────────────────────────
    score = details.get("score", 0)
    if isinstance(score, int) and score >= 75:
        slots = next_available()
        if slots:
            s = slots[0]
            return say(
                f"You're a great fit for FlowCRM! Ready to see it in action? "
                f"I can book a personalised demo for {s['date']} at {s['time']}.",
                f"आप FlowCRM के लिए बिल्कुल सही हैं! {s['date']} को {s['time']} बजे डेमो बुक करें?"
            )
    return say(
        "Thanks for sharing. Which feature would make the biggest difference to your team?",
        "जानकारी के लिए धन्यवाद। आपकी टीम के लिए कौन सी सुविधा सबसे ज़रूरी है?"
    )
