# Security and data flow

Keep the MVP bound to localhost and set a strong APP_ACCESS_KEY for live use. The API issues a room-scoped LiveKit token and keeps provider credentials server-side. The browser stores the workspace key for its current session. The MVP uses a shared workspace key. A shared deployment needs individual authentication, roles and tenant isolation.

Live audio passes through LiveKit and reaches Groq for transcription. Conversation context reaches the configured text model, and reply text reaches Edge-TTS. The prototype stores transcripts, extracted details, and LangGraph checkpoints on disk. It does not record raw audio. Obtain consent appropriate to the use case and use test identities for evaluation.

Product documents and customer transcripts are treated as inputs. Model output is parsed as structured data. The sales graph exposes no arbitrary database commands or external business actions. Product data should be reviewed before indexing. For production, add per-tenant access controls, HTTPS, retention and deletion workflows, PII controls, protected storage and audit trails.
