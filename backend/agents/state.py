from typing import TypedDict, Optional

class State(TypedDict, total=False):
    call_id: str
    message: str
    mode: str
    context: list
    interpretation: dict
    reply: str
    language: str
    sources: list[str]
    sentiment: str
    objections: list[str]
    appointment: Optional[dict]   # set when agent books a slot mid-turn
