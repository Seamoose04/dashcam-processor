import os
import psycopg2

# -----------------------------------------------------------------------------
# CONFIGURATION (edit if needed)
# -----------------------------------------------------------------------------
DB_HOST = os.getenv("POSTGRES_HOST", "localhost")
DB_NAME = os.getenv("POSTGRES_DB", "dashcam_final")
DB_USER = os.getenv("POSTGRES_USER", "dashcam")
DB_PASS = os.getenv("POSTGRES_PASSWORD", "dashpass")
DB_PORT = int(os.getenv("POSTGRES_PORT", 5432))

# -----------------------------------------------------------------------------
# CONNECT
# -----------------------------------------------------------------------------
print(f"[SETUP] Connecting to Postgres at {DB_HOST}:{DB_PORT}/{DB_NAME} ...")

conn = psycopg2.connect(
    host=DB_HOST,
    database=DB_NAME,
    user=DB_USER,
    password=DB_PASS,
    port=DB_PORT
)
conn.autocommit = True
cur = conn.cursor()

# -----------------------------------------------------------------------------
# CREATE EXTENSIONS
# -----------------------------------------------------------------------------
print("[SETUP] Enabling pg_trgm extension if missing...")
cur.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm;")

# -----------------------------------------------------------------------------
# CREATE TABLE
# -----------------------------------------------------------------------------
print("[SETUP] Creating vehicles table...")

cur.execute("""
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    track_id INTEGER,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    ts TIMESTAMPTZ NOT NULL,

    final_plate TEXT NOT NULL,
    plate_confidence REAL,

    car_bbox JSONB NOT NULL,
    plate_bbox JSONB NOT NULL,

    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")

# -----------------------------------------------------------------------------
# CREATE INDEXES
# -----------------------------------------------------------------------------
print("[SETUP] Creating indexes...")

cur.execute("CREATE INDEX IF NOT EXISTS vehicles_plate_idx ON vehicles(final_plate);")
cur.execute("CREATE INDEX IF NOT EXISTS vehicles_ts_idx ON vehicles(ts);")
cur.execute("""
    CREATE INDEX IF NOT EXISTS vehicles_plate_trgm_idx 
    ON vehicles USING GIN (final_plate gin_trgm_ops);
""")
# Ensure newer columns exist even if table was created before this script was updated.
cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS track_id INTEGER;")
cur.execute("CREATE INDEX IF NOT EXISTS vehicles_track_idx ON vehicles(track_id);")

# -----------------------------------------------------------------------------
# DONE
# -----------------------------------------------------------------------------
print("[SETUP] Final DB setup complete!")
cur.close()
conn.close()
