import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import date
from contextlib import contextmanager


class _ConnWrapper:
    """Тонкая обёртка, чтобы conn.execute(...).fetchone() работал как в sqlite3."""
    def __init__(self, conn):
        self._conn = conn

    def execute(self, sql, params=()):
        cur = self._conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(sql, params)
        return cur

    def executescript(self, script):
        cur = self._conn.cursor()
        cur.execute(script)
        cur.close()


class Database:
    def __init__(self, dsn):
        """dsn — строка подключения Postgres, например из DATABASE_URL (Neon/Supabase/Railway)."""
        self.dsn = dsn
        self._init_db()

    @contextmanager
    def _conn(self):
        conn = psycopg2.connect(self.dsn)
        try:
            yield _ConnWrapper(conn)
            conn.commit()
        finally:
            conn.close()

    def _init_db(self):
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    name TEXT,
                    points INTEGER DEFAULT 0,
                    created_at DATE DEFAULT CURRENT_DATE
                );
                CREATE TABLE IF NOT EXISTS experiments (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    plant TEXT,
                    start_date DATE,
                    active INTEGER DEFAULT 1
                );
                CREATE TABLE IF NOT EXISTS waterings (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    watered_on DATE
                );
                CREATE TABLE IF NOT EXISTS heights (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    day INTEGER,
                    height REAL
                );
                CREATE TABLE IF NOT EXISTS diary_entries (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    day INTEGER,
                    note TEXT
                );
                CREATE TABLE IF NOT EXISTS achievements (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT,
                    ach_id TEXT,
                    UNIQUE(user_id, ach_id)
                );
            """)

    def register_user(self, user_id, name):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO users (user_id, name) VALUES (%s, %s) ON CONFLICT (user_id) DO NOTHING",
                (user_id, name)
            )

    def get_points(self, user_id):
        with self._conn() as conn:
            row = conn.execute("SELECT points FROM users WHERE user_id=%s", (user_id,)).fetchone()
            return row["points"] if row else 0

    def add_points(self, user_id, pts):
        with self._conn() as conn:
            conn.execute("UPDATE users SET points = points + %s WHERE user_id=%s", (pts, user_id))

    def get_active_users(self):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT u.user_id, u.name FROM users u JOIN experiments e ON u.user_id = e.user_id WHERE e.active=1"
            ).fetchall()
            return [dict(r) for r in rows]

    def start_experiment(self, user_id, plant):
        with self._conn() as conn:
            conn.execute("UPDATE experiments SET active=0 WHERE user_id=%s", (user_id,))
            conn.execute(
                "INSERT INTO experiments (user_id, plant, start_date) VALUES (%s, %s, %s)",
                (user_id, plant, date.today().isoformat())
            )

    def get_experiment(self, user_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT * FROM experiments WHERE user_id=%s AND active=1", (user_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_experiment_day(self, user_id):
        exp = self.get_experiment(user_id)
        if not exp:
            return 0
        start = exp["start_date"]
        if isinstance(start, str):
            start = date.fromisoformat(start)
        return (date.today() - start).days + 1

    def log_watering(self, user_id):
        today = date.today().isoformat()
        with self._conn() as conn:
            existing = conn.execute(
                "SELECT id FROM waterings WHERE user_id=%s AND watered_on=%s", (user_id, today)
            ).fetchone()
            if existing:
                return True
            conn.execute("INSERT INTO waterings (user_id, watered_on) VALUES (%s, %s)", (user_id, today))
            return False

    def watered_today(self, user_id):
        today = date.today().isoformat()
        with self._conn() as conn:
            row = conn.execute(
                "SELECT id FROM waterings WHERE user_id=%s AND watered_on=%s", (user_id, today)
            ).fetchone()
            return row is not None

    def get_watering_count(self, user_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) as cnt FROM waterings WHERE user_id=%s", (user_id,)
            ).fetchone()
            return row["cnt"] if row else 0

    def log_height(self, user_id, height):
        day = self.get_experiment_day(user_id)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO heights (user_id, day, height) VALUES (%s, %s, %s)", (user_id, day, height)
            )

    def get_last_height(self, user_id):
        with self._conn() as conn:
            row = conn.execute(
                "SELECT height FROM heights WHERE user_id=%s ORDER BY id DESC LIMIT 1", (user_id,)
            ).fetchone()
            return row["height"] if row else None

    def get_heights(self, user_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT day, height FROM heights WHERE user_id=%s ORDER BY id", (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def add_diary_entry(self, user_id, day, note):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO diary_entries (user_id, day, note) VALUES (%s, %s, %s)", (user_id, day, note)
            )

    def get_diary_entries(self, user_id):
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT day, note FROM diary_entries WHERE user_id=%s ORDER BY id", (user_id,)
            ).fetchall()
            return [dict(r) for r in rows]

    def grant_achievement(self, user_id, ach_id):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO achievements (user_id, ach_id) VALUES (%s, %s) ON CONFLICT (user_id, ach_id) DO NOTHING",
                (user_id, ach_id)
            )

    def get_achievements(self, user_id):
        with self._conn() as conn:
            rows = conn.execute("SELECT ach_id FROM achievements WHERE user_id=%s", (user_id,)).fetchall()
            return [r["ach_id"] for r in rows]
