CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS transcription_job (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_path TEXT NOT NULL,
    source_hash TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    processing_mode TEXT NOT NULL CHECK (processing_mode IN ('asr', 'asr-multitrack', 'diarize')),
    tracks JSONB,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING', 'PROCESSING', 'COMPLETED', 'FAILED')),
    engine TEXT,
    engine_version TEXT,
    model_name TEXT,
    language TEXT,
    alignment_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    diarization_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    metrics JSONB,
    last_progress_at TIMESTAMPTZ,
    progress_percent REAL,
    current_stage TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS transcription_job_status_idx ON transcription_job (status);
