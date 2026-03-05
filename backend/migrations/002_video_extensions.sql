-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS video_recordings (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id),
    filename VARCHAR(255) NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    file_size INTEGER NOT NULL,
    duration INTEGER,
    transcript TEXT,
    transcript_embedding VECTOR(1536),
    summary TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_video_recordings_user_id
ON video_recordings(user_id);

CREATE INDEX IF NOT EXISTS idx_video_recordings_created_at
ON video_recordings(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_video_recordings_transcript_embedding
ON video_recordings
USING ivfflat (transcript_embedding vector_cosine_ops)
WITH (lists = 100);
