import os
import time
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

class FinalDB:
    def __init__(self):
        host = os.getenv("POSTGRES_HOST", "finaldb")
        port = int(os.getenv("POSTGRES_PORT", "5432"))
        dbname = os.getenv("POSTGRES_DB", "dashcam_final")
        user = os.getenv("POSTGRES_USER", "dashcam")
        password = os.getenv("POSTGRES_PASSWORD", "dashpass")

        # Retry a few times to avoid a race where Postgres is still booting.
        attempts = 8
        delay = 2
        last_err = None
        for attempt in range(1, attempts + 1):
            try:
                self.conn = psycopg2.connect(
                    host=host,
                    port=port,
                    database=dbname,
                    user=user,
                    password=password,
                    cursor_factory=psycopg2.extras.RealDictCursor,
                )
                self.conn.autocommit = True
                print(f"[DB] Connected to {host}:{port}/{dbname} as {user}")
                break
            except psycopg2.OperationalError as exc:
                last_err = exc
                if attempt == attempts:
                    raise
                wait = delay * attempt
                print(
                    f"[DB] Connection attempt {attempt}/{attempts} failed ({exc}). "
                    f"Retrying in {wait}s..."
                )
                time.sleep(wait)

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

    def motion_window(
        self,
        global_id: str,
        *,
        start_frame: int,
        end_frame: int,
        video_id: Optional[str] = None,
    ) -> Dict[int, Dict[str, Any]]:
        """
        Fetch per-frame motion rows for a global_id in the given frame window.
        Returns a mapping of frame_idx -> row for fast lookup during rendering.
        """
        params: Dict[str, Any] = {"gid": global_id, "start": start_frame, "end": end_frame}
        filters = ["global_id = %(gid)s", "frame_idx BETWEEN %(start)s AND %(end)s"]
        if video_id:
            filters.append("video_id = %(vid)s")
            params["vid"] = video_id

        where_clause = f"WHERE {' AND '.join(filters)}"

        with self.conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT
                    frame_idx,
                    bbox,
                    vx,
                    vy,
                    speed_px_s,
                    heading_deg
                FROM track_motion
                {where_clause}
                ORDER BY frame_idx ASC;
                """,
                params,
            )
            rows = cur.fetchall() or []

        motion_map: Dict[int, Dict[str, Any]] = {}

        def _normalize_bbox(bbox: Any):
            if bbox is None:
                return None
            if isinstance(bbox, (list, tuple)):
                return [float(v) for v in bbox]
            return bbox

        for row in rows:
            entry = dict(row)
            entry["bbox"] = _normalize_bbox(entry.get("bbox"))
            frame_idx = entry.get("frame_idx")
            if frame_idx is not None:
                motion_map[int(frame_idx)] = entry

        return motion_map

    # ------------------------------------------------------------------
    # Global ID helpers
    # ------------------------------------------------------------------

    def search_global_ids(
        self,
        query: Optional[str] = None,
        *,
        limit: int = 25,
        offset: int = 0,
    ) -> List[Dict[str, Any]]:
        """
        List tracks by global_id, optionally fuzzy matched.
        """
        params: Dict[str, Any] = {"limit": limit, "offset": offset}
        filters = []
        order_by = "ORDER BY created_at DESC"

        if query:
            params["q"] = query
            params["pattern"] = f"%{query}%"
            filters.append("(global_id ILIKE %(pattern)s OR similarity(global_id, %(q)s) > 0)")
            order_by = "ORDER BY similarity(global_id, %(q)s) DESC NULLS LAST, created_at DESC"

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""

        sql = f"""
            SELECT
                global_id,
                video_id,
                track_id,
                first_frame_idx,
                video_ts_frame,
                video_path,
                video_filename,
                created_at
            FROM tracks
            {where_clause}
            {order_by}
            LIMIT %(limit)s
            OFFSET %(offset)s;
        """
        with self.conn.cursor() as cur:
            cur.execute(sql, params)
            rows = cur.fetchall() or []
        return [dict(r) for r in rows]

    def get_latest_vehicle_for_global(self, global_id: str) -> Optional[Dict[str, Any]]:
        """
        Fetch the most recent vehicle row for a given global_id.
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
                WHERE global_id = %(gid)s
                ORDER BY ts DESC
                LIMIT 1;
                """,
                {"gid": global_id},
            )
            row = cur.fetchone()
        return self._serialize_vehicle(row) if row else None

    def get_vehicle_for_global_frame(self, global_id: str, frame_idx: int) -> Optional[Dict[str, Any]]:
        """
        Fetch a vehicle row for a given global_id and frame_idx.
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
                WHERE global_id = %(gid)s AND frame_idx = %(frame)s
                ORDER BY ts DESC
                LIMIT 1;
                """,
                {"gid": global_id, "frame": frame_idx},
            )
            row = cur.fetchone()
        return self._serialize_vehicle(row) if row else None

    def get_vehicle_for_global_nearest_frame(self, global_id: str, frame_idx: int) -> Optional[Dict[str, Any]]:
        """
        Fetch the closest vehicle row to the requested frame_idx for a global_id.
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
                WHERE global_id = %(gid)s
                ORDER BY abs(frame_idx - %(frame)s) ASC, frame_idx ASC
                LIMIT 1;
                """,
                {"gid": global_id, "frame": frame_idx},
            )
            row = cur.fetchone()
        return self._serialize_vehicle(row) if row else None

    def get_fastest_frame_idx(self, global_id: str) -> Optional[int]:
        """
        Return the frame_idx with highest speed for a track.
        """
        with self.conn.cursor() as cur:
            cur.execute(
                """
                SELECT frame_idx
                FROM track_motion
                WHERE global_id = %(gid)s
                ORDER BY speed_px_s DESC NULLS LAST, frame_idx ASC
                LIMIT 1;
                """,
                {"gid": global_id},
            )
            row = cur.fetchone()
        if not row:
            return None
        if isinstance(row, dict):
            return row.get("frame_idx")
        return row[0] if row else None

db = FinalDB()
