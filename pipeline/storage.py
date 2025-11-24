# pipeline/storage.py

import sqlite3
import json
import os
from typing import Optional, Any, Tuple, List

from pipeline.task import Task, TaskCategory


class SQLiteStorage:
    """
    Multiprocessing-safe SQLite storage wrapper.

    IMPORTANT: We do NOT store raw `task.payload` here, only a small
    JSON-serializable *reference* taken from `task.meta['payload_ref']`.
    """

    def __init__(self, path: str = "pipeline.db"):
        init_db = not os.path.exists(path)
        self.path = path

        self.conn = sqlite3.connect(
            self.path,
            check_same_thread=False,
            timeout=5.0,
            isolation_level=None,
        )

        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.execute("PRAGMA busy_timeout = 5000;")
        self.conn.execute("PRAGMA temp_store=MEMORY;")
        self.conn.execute("PRAGMA mmap_size=30000000000;")

        self.cursor = self.conn.cursor()

        if init_db:
            self._init_schema()

    def _init_schema(self):
        self.cursor.execute("""
            CREATE TABLE tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT,
                payload TEXT,   -- interpreted as payload_ref (not the real payload)
                priority INTEGER,
                video_id TEXT,
                frame_idx INTEGER,
                track_id INTEGER,
                meta TEXT,
                dependencies TEXT,      -- NEW COLUMN
                status TEXT
            )
        """)

        self.cursor.execute("""
            CREATE TABLE results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id INTEGER,
                result TEXT,
                handled INTEGER DEFAULT 0
            )
        """)

        self.cursor.execute("""
            CREATE TABLE summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                frame_idx INTEGER,
                final_plate TEXT,
                car_bbox TEXT,
                plate_bbox TEXT,
                ts REAL
            )
        """)
        self.conn.commit()

    # ---------------- Task persistence (unchanged except using payload_ref) ----------------

    def save_task(self, task: Task) -> int:
        payload_ref = task.meta.get("payload_ref", None)
        dependencies = task.meta.get("dependencies", None)

        self.cursor.execute("""
            INSERT INTO tasks
            (category, payload, priority, video_id, frame_idx, track_id, meta, dependencies, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'queued')
        """, (
            task.category.value,
            json.dumps(payload_ref),
            task.priority,
            task.video_id,
            task.frame_idx,
            task.track_id,
            json.dumps(task.meta),
            json.dumps(dependencies) if dependencies is not None else None,
        ))
        self.conn.commit()
        return self.cursor.lastrowid or 0

    def load_pending_tasks(self) -> list[tuple[int, Task]]:
        self.cursor.execute("""
            SELECT id, category, payload, priority, video_id, frame_idx, track_id, meta, dependencies
            FROM tasks WHERE status='queued'
        """)
        rows = self.cursor.fetchall()

        pending: list[tuple[int, Task]] = []
        for tid, cat, payload_ref_json, p, vid, fidx, ttrack, meta_json, dep_json in rows:
            meta = json.loads(meta_json)
            payload_ref = json.loads(payload_ref_json) if payload_ref_json else None
            if payload_ref is not None:
                meta.setdefault("payload_ref", payload_ref)

            if dep_json:
                dependencies = json.loads(dep_json)
                meta.setdefault("dependencies", dependencies)

            task = Task(
                category=TaskCategory(cat),
                payload=None,
                priority=p,
                video_id=vid,
                frame_idx=fidx,
                track_id=ttrack,
                meta=meta,
            )
            pending.append((tid, task))

        return pending

    def mark_task_done(self, task_id: int):
        self.cursor.execute("UPDATE tasks SET status='done' WHERE id=?", (task_id,))
        self.conn.commit()

    def mark_task_running(self, task_id: int):
        """Mark a task as running once a worker pops it from the queue."""
        self.cursor.execute("UPDATE tasks SET status='running' WHERE id=?", (task_id,))
        self.conn.commit()

    # ---------------- Results ----------------

    def save_result(self, task_id: int, result: Any):
        """Save a completed task result, marked as unhandled for dispatcher."""
        self.cursor.execute("""
            INSERT INTO results (task_id, result, handled)
            VALUES (?, ?, 0)
        """, (task_id, json.dumps(result)))
        self.conn.commit()

    # -------- Dispatcher helpers --------

    def fetch_unhandled_results(self, limit: int = 100) -> List[Tuple[int, int, TaskCategory, Task, Any]]:
        self.cursor.execute("""
            SELECT
                r.id,
                r.task_id,
                r.result,
                t.category,
                t.payload,
                t.priority,
                t.video_id,
                t.frame_idx,
                t.track_id,
                t.meta,
                t.dependencies
            FROM results r
            JOIN tasks t ON r.task_id = t.id
            WHERE r.handled = 0
            LIMIT ?
        """, (limit,))
        rows = self.cursor.fetchall()

        items: List[Tuple[int, int, TaskCategory, Task, Any]] = []
        for result_id, task_id, result_json, cat, payload_ref_json, p, vid, fidx, ttrack, meta_json, dep_json in rows:
            meta = json.loads(meta_json)
            payload_ref = json.loads(payload_ref_json) if payload_ref_json else None
            if payload_ref is not None:
                meta.setdefault("payload_ref", payload_ref)

            if dep_json:
                dependencies = json.loads(dep_json)
                meta.setdefault("dependencies", dependencies)

            task = Task(
                category=TaskCategory(cat),
                payload=None,
                priority=p,
                video_id=vid,
                frame_idx=fidx,
                track_id=ttrack,
                meta=meta,
            )
            result_obj = json.loads(result_json)
            items.append((result_id, task_id, TaskCategory(cat), task, result_obj))

        return items

    def mark_result_handled(self, result_id: int):
        self.cursor.execute("UPDATE results SET handled = 1 WHERE id=?", (result_id,))
        self.conn.commit()

    # -------- Backlog helpers --------

    def count_tasks_by_category(
        self,
        categories: list[TaskCategory] | None = None,
        statuses: tuple[str, ...] = ("queued", "running"),
    ) -> dict[TaskCategory, int]:
        """
        Return {TaskCategory: count} for requested categories (or all), filtered by status.
        Default counts both queued and running tasks so we see in-flight work.
        """
        params: list = list(statuses)
        where_parts = ["status IN ({})".format(",".join("?" for _ in statuses))]

        if categories:
            where_parts.append("category IN ({})".format(",".join("?" for _ in categories)))
            params.extend(cat.value for cat in categories)

        where = " AND ".join(where_parts)

        self.cursor.execute(f"""
            SELECT category, COUNT(*)
            FROM tasks
            WHERE {where}
            GROUP BY category
        """, params)

        rows = self.cursor.fetchall()
        counts: dict[TaskCategory, int] = {}
        for cat, cnt in rows:
            counts[TaskCategory(cat)] = cnt
        return counts

    def count_unhandled_results_by_category(
        self,
        categories: list[TaskCategory] | None = None,
    ) -> dict[TaskCategory, int]:
        """
        Return {TaskCategory: count_of_unhandled_results} for the given categories
        (or all categories if None).
        Useful to detect result backlog that has not yet been dispatched into downstream tasks.
        """
        params: list = []
        where = ""
        if categories:
            where = "WHERE t.category IN ({})".format(",".join("?" for _ in categories))
            params.extend(cat.value for cat in categories)

        self.cursor.execute(f"""
            SELECT t.category, COUNT(*)
            FROM results r
            JOIN tasks t ON r.task_id = t.id
            WHERE r.handled = 0
            {('AND ' + where[6:]) if where else ''}
            GROUP BY t.category
        """, params)

        rows = self.cursor.fetchall()
        counts: dict[TaskCategory, int] = {}
        for cat, cnt in rows:
            counts[TaskCategory(cat)] = cnt
        return counts

    def has_other_active_or_unhandled_dependents(
        self,
        payload_ref: str,
        excluding_task_id: int,
    ) -> bool:
        """
        Return True if there exists ANY other task (not excluding_task_id) that:
        - has dependencies containing this payload_ref, AND
        - is either not done yet, OR has a result that is not yet handled.
        """

        pattern = f'%"{payload_ref}"%'  # crude but works for JSON list of strings

        self.cursor.execute("""
            SELECT COUNT(*)
            FROM tasks t
            LEFT JOIN results r ON r.task_id = t.id
            WHERE t.id != ?
              AND t.dependencies LIKE ?
              AND (
                    t.status != 'done'
                    OR (r.id IS NOT NULL AND r.handled = 0)
                  )
        """, (excluding_task_id, pattern))

        row = self.cursor.fetchone()
        count = row[0] if row else 0
        return count > 0
