"""Voice agent – rewritten for livekit-agents 1.8.x.

Key changes from prior version
-------------------------------
* AgentSession.start() takes room= as keyword; ctx.connect() must be called
  BEFORE session.start() so the room transport is ready.
* The conversation_item_added event item is now a ChatMessage (pydantic model),
  not a plain object.  Use item.text_content and item.role.
* llm_node must be an async generator that *yields* str chunks, NOT a regular
  method that yields once.  Returning None suppresses the LLM entirely and
  skips TTS – which is what we want when we do our own reply via the graph.
* AgentSession.say() is used to push the reply back as audio.
* silero VAD is loaded in prewarm and stored in process.userdata.
"""
import asyncio
import logging
import os
import uuid

from livekit.agents import Agent, AgentServer, AgentSession, JobContext, cli
from livekit.agents import llm as agents_llm
from livekit.plugins import groq, silero

from ..config import LIVE
from ..agents.graph import turn, call_lock, graph
from ..agents.nodes import language
from ..rag.retrieval import semantic
from ..database import db, init, add_message
from ..services.summarizer import finish
from .edge_tts_adapter import EdgeTTS

log = logging.getLogger(__name__)

server = AgentServer(num_idle_processes=1, initialize_process_timeout=60.0)
GREETING = "Hi there! I'm Maya from FlowCRM. How can I help you today?"


# ── prewarm ───────────────────────────────────────────────────────────────────

def prewarm(process):
    process.userdata["vad"] = silero.VAD.load(
        min_speech_duration=0.3,
        min_silence_duration=0.7,
        activation_threshold=0.65,
    )
    graph()   # warm up LangGraph checkpointer
    if LIVE:
        semantic()  # preload SentenceTransformer + FAISS index so first turn is fast

server.setup_fnc = prewarm


# ── agent ─────────────────────────────────────────────────────────────────────

class SalesAgent(Agent):
    """
    Custom agent that bypasses the LLM plugin entirely and routes every
    customer utterance through the LangGraph sales pipeline.
    """

    def __init__(self, call_id: str, session: AgentSession):
        super().__init__(instructions=GREETING)
        self.call_id = call_id
        self._session = session

    async def llm_node(
        self,
        chat_ctx: agents_llm.ChatContext,
        tools: list,
        model_settings,
    ):
        """
        Override the LLM node.

        1. Extract the latest user utterance from the ChatContext.
        2. Run the LangGraph sales turn (blocking → thread).
        3. Yield the reply string so the TTS node picks it up.
        4. Return early (yield nothing) if the call is already ended.
        """
        # Find the last user message
        customer_text = None
        for item in reversed(chat_ctx.items):
            if isinstance(item, agents_llm.ChatMessage) and item.role == "user":
                customer_text = item.text_content
                break

        if not customer_text:
            return   # nothing to respond to

        def run_turn():
            with call_lock(self.call_id):
                with db() as con:
                    state = con.execute(
                        "SELECT ended FROM calls WHERE id=?", (self.call_id,)
                    ).fetchone()
                if state and not state["ended"]:
                    return turn(self.call_id, customer_text, "live")
            return None

        try:
            result = await asyncio.to_thread(run_turn)
        except Exception:
            log.exception("Sales turn failed for call %s", self.call_id)
            result = None

        if result and result.get("reply"):
            log.info("Sales reply for call %s: %s", self.call_id, result["reply"][:80])
            yield result["reply"]


# ── entrypoint ────────────────────────────────────────────────────────────────

@server.rtc_session(agent_name="flowcrm")
async def entrypoint(ctx: JobContext):
    if not LIVE:
        return

    # Validate the room name encodes a live call UUID
    room_name = ctx.job.room.name
    call_id = room_name.removeprefix("flowcrm-")
    try:
        if uuid.UUID(hex=call_id).hex != call_id:
            log.warning("Invalid call_id in room name: %s", room_name)
            return
    except ValueError:
        log.warning("Non-UUID room name: %s", room_name)
        return

    with db() as con:
        call = con.execute(
            "SELECT mode, ended FROM calls WHERE id=?", (call_id,)
        ).fetchone()
    if not call or call["mode"] != "live" or call["ended"]:
        log.warning("Call %s not active/live: %s", call_id, dict(call) if call else None)
        return

    log.info("Starting live voice session for call %s", call_id)

    # ── build session ─────────────────────────────────────────────────────────
    session = AgentSession(
        tts=EdgeTTS(),
        stt=groq.STT(
            model=os.getenv("GROQ_STT_MODEL") or "whisper-large-v3-turbo",
            detect_language=True,
        ),
        vad=ctx.proc.userdata["vad"],
        llm=groq.LLM(model=os.getenv("GROQ_LLM_MODEL") or "openai/gpt-oss-120b"),
        turn_detection="vad",
        preemptive_generation=False,
        min_endpointing_delay=0.7,
        allow_interruptions=True,
        min_interruption_duration=0.6,
    )

    agent = SalesAgent(call_id=call_id, session=session)

    # ── persist assistant messages to our DB ──────────────────────────────────
    @session.on("conversation_item_added")
    def on_item(event):
        item = event.item
        if not isinstance(item, agents_llm.ChatMessage):
            return
        if item.role == "assistant" and item.text_content:
            add_message(
                call_id,
                "assistant",
                item.text_content,
                language(item.text_content),
                getattr(item, "interrupted", False),
            )

    # ── cleanup on session end ────────────────────────────────────────────────
    async def cleanup():
        await asyncio.to_thread(lambda: _finalize(call_id))

    ctx.add_shutdown_callback(cleanup)

    # ── connect room first, then start session ────────────────────────────────
    await ctx.connect()
    await ctx.wait_for_participant()

    await session.start(agent=agent, room=ctx.room)

    # Say greeting without interruption so initial mic noise doesn't abort it
    session.say(GREETING, allow_interruptions=False)


def _finalize(call_id: str):
    with call_lock(call_id):
        finish(call_id)


if __name__ == "__main__":
    init()
    cli.run_app(server)
