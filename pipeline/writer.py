# pipeline/writer.py

import os
import psycopg2
import json
from datetime import datetime, timezone

from dotenv import load_dotenv
load_dotenv()

class Writer:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "localhost"),
            database=os.getenv("POSTGRES_DB", "dashcam_final"),
            user=os.getenv("POSTGRES_USER", "dashcam"),
            password=os.getenv("POSTGRES_PASSWORD", "dashpass"),
            port=int(os.getenv("POSTGRES_PORT", "5432")),
        )
        self.conn.autocommit = True
        self.cur = self.conn.cursor()

    def write_vehicle(
        self,
        video_id: str,
        frame_idx: int,
        final_plate: str,
        conf: float,
        car_bbox,
        plate_bbox,
        timestamp=None,
    ):
        """
        Insert a completed recognition result into final Postgres DB.
        """

        if timestamp is None:
            # fallback: use processing time
            timestamp = datetime.now(timezone.utc)

        self.cur.execute(
            """
            INSERT INTO vehicles 
            (video_id, frame_idx, ts, final_plate, plate_confidence, car_bbox, plate_bbox)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                video_id,
                frame_idx,
                timestamp,
                final_plate,
                conf,
                json.dumps(car_bbox),
                json.dumps(plate_bbox),
            ),
        )

writer = Writer()
