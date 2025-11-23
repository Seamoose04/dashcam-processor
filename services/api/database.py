import os
import psycopg2

class FinalDB:
    def __init__(self):
        self.conn = psycopg2.connect(
            host=os.getenv("POSTGRES_HOST", "finaldb"),
            database=os.getenv("POSTGRES_DB", "dashcam_final"),
            user=os.getenv("POSTGRES_USER", "dashcam"),
            password=os.getenv("POSTGRES_PASSWORD", "dashpass"),
        )
        self.conn.autocommit = True
        self.cur = self.conn.cursor()

    def test(self):
        self.cur.execute("SELECT NOW()")
        return self.cur.fetchone()[0]

db = FinalDB()
