from functools import lru_cache
from threading import Lock
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
from ..config import DATA
from .state import State
from .nodes import interpret, sales

LOCKS = tuple(Lock() for _ in range(64))

def call_lock(call_id):
    return LOCKS[hash(call_id) % len(LOCKS)]

@lru_cache(maxsize=1)
def graph():
    pipeline = StateGraph(State)
    pipeline.add_node("interpret", interpret)
    pipeline.add_node("sales", sales)
    pipeline.add_edge(START,"interpret")
    pipeline.add_edge("interpret","sales")
    pipeline.add_edge("sales",END)
    con = sqlite3.connect(DATA / "checkpoints.db", check_same_thread=False)
    return pipeline.compile(checkpointer=SqliteSaver(con))

def turn(call_id, text, mode):
    return graph().invoke({"call_id":call_id,"message":text.strip(),"mode":mode},
                          {"configurable":{"thread_id":call_id}})
