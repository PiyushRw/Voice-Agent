# FlowCRM AI Sales Voice Agent

A web-based, bilingual (**English & Devanagari Hindi**) AI sales representative (**Maya**) for a fictional CRM product. It answers product questions from company documents, remembers customer requirements, qualifies leads using BANT + engagement signals, identifies sentiment and objections, books conflict-free demo appointments, exposes CRM pipeline APIs, and produces a call summary for sales follow-up.

| Capability | Live voice & AI chat | Offline text demo |
|---|---|---|
| Conversation | LiveKit Cloud WebRTC, Silero VAD (barge-in), Groq Whisper (`whisper-large-v3-turbo`), Edge-TTS (`en-IN` / `hi-IN`) + in-call text composer | Typed conversation |
| Response | LangGraph (`interpret -> sales`) with Groq LLM (`openai/gpt-oss-120b`) and Gemini (`gemini-2.5-flash`) fallback | LangGraph with deterministic rules |
| Knowledge | Multilingual MiniLM (`paraphrase-multilingual-MiniLM-L12-v2`) and FAISS (`IndexFlatIP`) over `knowledge_base/` | Keyword matching over `knowledge_base/` |
| Lead & Booking | BANT (`90` pts) + contact details (`+15`) + confirmed demo (`+35`), capped at `100`; date-confirmed slot booking | Rule-based BANT + slot booking |
| Sales Output | Sentiment, objections, call summary, next action, CRM pipeline (`/api/crm/*`), and appointments (`/api/appointments/*`) | Same tables and dashboard |
| Storage | SQLite WAL (`data/sales.db`, `data/checkpoints.db`) | Same tables with `demo` mode |

## Start on Windows

From the project directory, with Python 3.12 and Node.js 22 or later:

```powershell
Copy-Item .env.example .env
uv venv --python 3.12
uv pip install -p .venv\Scripts\python.exe -r requirements.txt
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run build
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. For frontend development, run `npm.cmd --prefix frontend run dev` in a separate terminal while FastAPI is running.

## Enable live voice

1. Set `SALES_MODE=live`, `GROQ_LLM_MODEL=openai/gpt-oss-120b`, `GROQ_STT_MODEL=whisper-large-v3-turbo`, and fill in `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and `GROQ_API_KEY` in `.env`. An optional `GOOGLE_API_KEY` enables Gemini (`gemini-2.5-flash`) fallback. (All voice and RAG dependencies are already included in `requirements.txt`.)
2. Run `.venv\Scripts\python.exe -m backend.voice.agent download-files` to download the Silero VAD model. Multilingual MiniLM downloads on first startup and is preloaded in `prewarm()`.
3. Start the FastAPI server and run `.venv\Scripts\python.exe -m backend.voice.agent dev` in a second terminal. Wait for `registered worker` before clicking **Start voice call**.
4. Click **Start voice call** (or **Start text chat**), grant microphone access to localhost, and use headphones when testing barge-in interruption. Use fictional customer details because external providers process the call.

For Docker, copy `.env.example` to `.env` and run `docker compose up --build` for text mode. For live mode, set the credentials in `.env` and run `docker compose --profile voice up --build`.

## Evaluation walkthrough

1. Start a text chat (**💬 Start text chat**) and click **Share requirements**. The transcript captures Rahul's name, budget, decision-making authority, team need, and 30-day timeline (`90/100 · Hot`).
2. Click **Ask about pricing**. The response cites `pricing.md` and includes Starter (`₹999/month`) and Professional (`₹2,999/month`).
3. Ask *"Do you remember my budget?"* and verify the prior budget is recalled cleanly.
4. Click **Book a demo** (or ask to schedule for a specific date/time), confirm a slot, and verify the **📅 Demo booked** card appears without creating duplicate bookings.
5. Click **Share an objection**, click **End call**, and check the **Call summary** in **Call console**, **Call history**, and **Dashboard** (**Overview**, **Pipeline**, and **Appointments**).
6. Repeat with **🎙 Start voice call** in English and Hindi, test barge-in interruption, and use the in-call text composer to type details mid-call.

## Documentation & Reports

- [1-Page Report (Markdown)](Report.md) · [1-Page Report (DOCX)](Report.docx)
- [Architecture](docs/architecture.md) · [Scaling and costs](docs/scalability.md) · [Security](docs/security.md)
