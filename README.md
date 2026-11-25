# FlowCRM AI Sales Voice Agent

A web-based sales representative for a fictional CRM product. It answers product questions from company documents, remembers the customer's requirements, qualifies leads using BANT, identifies sentiment and objections, and produces a call summary for sales follow-up.

| Capability | Live voice | Text demo |
|---|---|---|
| Conversation | LiveKit, Silero VAD, Groq Whisper, Edge-TTS | Typed conversation |
| Response | LangGraph with Groq LLM and optional Gemini fallback | LangGraph with deterministic rules |
| Knowledge | Multilingual MiniLM and FAISS | Keyword matching over sample documents |
| Sales output | BANT, sentiment, objections, summary and next action | Rule-based equivalents |
| Storage | SQLite transcripts, sales data and checkpoints | Same tables with a separate mode |

## Start on Windows

From the project directory, with Python 3.12 and Node.js 22 or later:

```powershell
Copy-Item .env.example .env
uv venv --python 3.12
uv pip install -p .venv\Scripts\python.exe -r requirements.txt
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run build
.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1
```

Open http://127.0.0.1:8000. For frontend development, run `npm.cmd --prefix frontend run dev` in a separate terminal while FastAPI is running.

## Enable live voice

1. Install `requirements-live.txt` into the same environment.
2. Set `SALES_MODE=live`, choose a strong local `APP_ACCESS_KEY`, and fill in `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, and `GROQ_API_KEY`. The optional Google AI Studio key enables Gemini fallback for text inference.
3. Run `.venv\Scripts\python.exe -m backend.voice.agent download-files` to download the Silero model. Multilingual MiniLM downloads on the first worker startup.
4. Start the API and run `.venv\Scripts\python.exe -m backend.voice.agent dev` in a second terminal. Wait for the worker to register before clicking **Start voice call**.
5. Enter your access key under **Workspace access**, start a call, and grant microphone access to localhost. Use headphones when testing interruption. Use fictional customer details because external providers process the call.

For Docker, copy the environment file and run `docker compose up --build` for text mode. For live mode, set the same credentials in `.env`, then run `docker compose --profile voice up --build`.

## Evaluation walkthrough

1. Start a text demo and click **Share requirements**. The transcript should capture Rahul's name, budget, decision-making authority, team need and 30-day timeline. A lead with all four BANT criteria scores 100.
2. Click **Ask about pricing**. The response should cite `pricing.md` and include Professional pricing of ₹2,999/month.
3. Ask “Do you remember my budget?” and verify the prior budget is recalled.
4. Click **Share an objection**, end the call, and open **Call history**. Confirm the summary, sentiment, pricing objection and next action. Open **Dashboard** to check that completed calls and qualified leads include this session.
5. Repeat with live voice using the configured accounts. Switch from English to Hindi, speak over a longer reply to test barge-in, and check that the next reply addresses the interruption. Confirm the interrupted reply is marked in the transcript.

[Architecture](docs/architecture.md) · [Scaling and costs](docs/scalability.md) · [Security](docs/security.md)
