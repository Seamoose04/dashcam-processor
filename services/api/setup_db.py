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
# CREATE / ALTER VEHICLES TABLE
# -----------------------------------------------------------------------------
print("[SETUP] Creating vehicles table...")

cur.execute("""
CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    global_id TEXT,
    track_id INTEGER,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    video_ts_frame INTEGER,
    video_path TEXT,
    video_filename TEXT,

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
cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS global_id TEXT;")
cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS track_id INTEGER;")
cur.execute("CREATE INDEX IF NOT EXISTS vehicles_track_idx ON vehicles(track_id);")
cur.execute("CREATE INDEX IF NOT EXISTS vehicles_global_idx ON vehicles(global_id);")
cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS video_ts_frame INTEGER;")
cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS video_path TEXT;")
cur.execute("ALTER TABLE vehicles ADD COLUMN IF NOT EXISTS video_filename TEXT;")
cur.execute("CREATE INDEX IF NOT EXISTS vehicles_video_idx ON vehicles(video_id);")

# -----------------------------------------------------------------------------
# TRACKS TABLE (one row per track/global_id)
# -----------------------------------------------------------------------------
print("[SETUP] Creating tracks table...")
cur.execute("""
CREATE TABLE IF NOT EXISTS tracks (
    id SERIAL PRIMARY KEY,
    global_id TEXT UNIQUE NOT NULL,
    video_id TEXT NOT NULL,
    track_id INTEGER NOT NULL,
    frame_idx INTEGER,
    first_frame_idx INTEGER NOT NULL,
    video_ts_frame INTEGER,
    video_ts_ms DOUBLE PRECISION,
    video_path TEXT,
    video_filename TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")
cur.execute("CREATE INDEX IF NOT EXISTS tracks_global_idx ON tracks(global_id);")
cur.execute("CREATE INDEX IF NOT EXISTS tracks_video_idx ON tracks(video_id);")
cur.execute("CREATE INDEX IF NOT EXISTS tracks_frame_idx ON tracks(frame_idx);")
# Ensure newer columns exist even if table already existed.
cur.execute("ALTER TABLE tracks ADD COLUMN IF NOT EXISTS frame_idx INTEGER;")

# -----------------------------------------------------------------------------
# TRACK_MOTION TABLE (per-frame kinematics)
# -----------------------------------------------------------------------------
print("[SETUP] Creating track_motion table...")
cur.execute("""
CREATE TABLE IF NOT EXISTS track_motion (
    id SERIAL PRIMARY KEY,
    global_id TEXT NOT NULL,
    track_id INTEGER,
    video_id TEXT NOT NULL,
    frame_idx INTEGER NOT NULL,
    video_ts_frame INTEGER,
    video_ts_ms DOUBLE PRECISION,
    bbox JSONB,
    vx DOUBLE PRECISION,
    vy DOUBLE PRECISION,
    speed_px_s DOUBLE PRECISION,
    heading_deg DOUBLE PRECISION,
    age_frames INTEGER,
    conf REAL,
    video_path TEXT,
    video_filename TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
""")
cur.execute("CREATE INDEX IF NOT EXISTS track_motion_global_idx ON track_motion(global_id);")
cur.execute("CREATE INDEX IF NOT EXISTS track_motion_video_idx ON track_motion(video_id);")
cur.execute("CREATE INDEX IF NOT EXISTS track_motion_frame_idx ON track_motion(frame_idx);")

# -----------------------------------------------------------------------------
# DONE
# -----------------------------------------------------------------------------
print("[SETUP] Final DB setup complete!")
cur.close()
conn.close()
