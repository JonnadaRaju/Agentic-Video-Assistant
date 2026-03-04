-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Add AI fields to existing table
ALTER TABLE audio_recordings
ADD COLUMN IF NOT EXISTS transcript TEXT;

ALTER TABLE audio_recordings
ADD COLUMN IF NOT EXISTS transcript_embedding VECTOR(1536);

-- Vector index for faster semantic search
CREATE INDEX IF NOT EXISTS idx_audio_recordings_transcript_embedding
ON audio_recordings
USING ivfflat (transcript_embedding vector_cosine_ops)
WITH (lists = 100);

