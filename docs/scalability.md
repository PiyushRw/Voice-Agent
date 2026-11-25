# Scalability and commercial feasibility

Use the prototype to qualify inbound SMB software inquiries and give sales staff a structured handoff. A subscription with included conversation minutes and metered overage is one commercial model.

Capacity depends on simultaneous calls. For 100,000 registered users with 10,000 calls per day at 5 minutes each over a 10-hour window, expect about 84 average concurrent calls. A 3× peak factor implies roughly 250 concurrent calls. At 30 days, that workload produces approximately 1.5 million conversation minutes per month. This is a sizing example.

Move SQLite to PostgreSQL, checkpoint writes to shared storage, and post-call synthesis to a durable job queue. Use Redis where distributed session coordination is needed. Scale voice workers by concurrency and observed media load. Use tenant-aware pgvector or another managed vector index for independent customer catalogs. Monitor STT latency, first audio latency, interruption recovery, task completion and error rate. Load-test provider quotas, media egress, reconnects and queue backlogs at the modeled peak.

Monthly operating cost is fixed infrastructure plus WebRTC usage and egress, transcribed audio minutes, model input/output tokens, synthesized characters or seconds, and data storage. Multiply each measured usage unit by the contracted provider rate. Free quotas and the unofficial Edge-TTS service are suitable for evaluation subject to availability. Production requires provider capacity and a supported TTS service with a documented service agreement.
