# pipeline/writer.py

import os
import psycopg2
from psycopg2 import sql
import json
from datetime import datetime, timezone

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

        record = {
            "video_id": video_id,
            "frame_idx": frame_idx,
            "ts": timestamp,
            "final_plate": final_plate,
            "plate_confidence": conf,
            "car_bbox": car_bbox,
            "plate_bbox": plate_bbox,
        }

        self.write_record("vehicles", record)

    def write_record(self, table: str, record: dict):
        """
        Generic insert helper to support flexible final-write payloads.
        """
        if not table:
            raise ValueError("Table name is required for write_record")

        if not isinstance(record, dict) or not record:
            raise ValueError("Record must be a non-empty dict")

        columns = list(record.keys())
        values = [self._coerce_value(record[c]) for c in columns]

        query = sql.SQL("INSERT INTO {table} ({cols}) VALUES ({vals})").format(
            table=sql.Identifier(table),
            cols=sql.SQL(", ").join(sql.Identifier(c) for c in columns),
            vals=sql.SQL(", ").join(sql.Placeholder() for _ in columns),
        )

        self.cur.execute(query, values)

    @staticmethod
    def _coerce_value(value):
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return value

_writer = None

def get_writer():
    global _writer
    if _writer is None:
        _writer = Writer()
    return _writer
