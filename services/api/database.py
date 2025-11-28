import os
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

class FinalDB:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "finaldb"),
            database=os.getenv("POSTGRES_DB", "dashcam_final"),
            user=os.getenv("POSTGRES_USER", "dashcam"),
            password=os.getenv("POSTGRES_PASSWORD", "dashpass"),
            cursor_factory=psycopg2.extras.RealDictCursor,
        )
        self.conn.autocommit = True

    def test(self):
        with self.conn.cursor() as cur:
            cur.execute("SELECT NOW()")
            row = cur.fetchone()
            if not row:
                return None
            if isinstance(row, dict):
                # RealDictCursor returns a dict like {"now": <timestamp>}
                return next(iter(row.values()))
            return row[0]

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _serialize_vehicle(self, row: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalize DB row fields for JSON responses.
        """
        if row is None:
            return {}

        def _normalize_bbox(bbox: Any):
            if bbox is None:
                return None
            if isinstance(bbox, (list, tuple)):
                return [float(v) for v in bbox]
            return bbox  # leave as-is if JSON already decoded to dict

        row = dict(row)
        row["car_bbox"] = _normalize_bbox(row.get("car_bbox"))
        row["plate_bbox"] = _normalize_bbox(row.get("plate_bbox"))
        return row

    def search_vehicles(
        self,
        query: Optional[str] = None,
        *,
        limit: int = 25,
        offset: int = 0,
        video_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Search finalized vehicle rows by plate text (ILIKE + trigram similarity).
        If no query is provided, returns recent rows ordered by timestamp.
        """
        params: Dict[str, Any] = {
            "limit": limit,
            "offset": offset,
        }

        filters = []
        order_by = "ORDER BY ts DESC"

        if video_id:
            filters.append("video_id = %(video_id)s")
            params["video_id"] = video_id

        if query:
            params["q"] = query
            params["pattern"] = f"%{query}%"
            filters.append(
                "(final_plate ILIKE %(pattern)s OR similarity(final_plate, %(q)s) > 0)"
            )
            order_by = "ORDER BY similarity(final_plate, %(q)s) DESC NULLS LAST, ts DESC"

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        sql = f"""
            SELECT
                id,
                global_id,
                track_id,
                video_id,
                frame_idx,
                video_ts_frame,
                video_path,
                video_filename,
                ts,
                final_plate,
                plate_confidence,
                car_bbox,
                plate_bbox
            FROM vehicles
            {where_clause}
            {order_by}
            LIMIT %(limit)s
            OFFSET %(offset)s;
        """

        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []

        return [self._serialize_vehicle(r) for r in rows]

    def get_vehicle(self, vehicle_id: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a single vehicle record by id.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    id,
                    global_id,
                    track_id,
                    video_id,
                    frame_idx,
                    video_ts_frame,
                    video_path,
                    video_filename,
                    ts,
                    final_plate,
                    plate_confidence,
                    car_bbox,
                    plate_bbox
                FROM vehicles
                WHERE id = %(id)s;
                """,
                {"id": vehicle_id},
            )
            row = cur.fetchone()

        return self._serialize_vehicle(row) if row else None

    def recent_motion(self, global_id: str, *, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Return recent motion rows for a given global track id.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    frame_idx,
                    video_ts_frame,
                    video_ts_ms,
                    bbox,
                    vx,
                    vy,
                    speed_px_s,
                    heading_deg,
                    conf,
                    created_at
                FROM track_motion
                WHERE global_id = %(gid)s
                ORDER BY frame_idx DESC
                LIMIT %(limit)s;
                """,
                {"gid": global_id, "limit": limit},
            )
            rows = cur.fetchall() or []

        return [dict(r) for r in rows]

db = FinalDB()
