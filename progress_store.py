"""Local SQLite persistence. No network, model calls, or executable deserialization."""
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sqlite3

from learning_paths import PATHS


def today():
    return datetime.now().astimezone().date()


class ProgressStore:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript('''
                CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, payload TEXT NOT NULL, updated TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS activity (session TEXT, exercise INTEGER, language TEXT, topic TEXT,
                    passed INTEGER, total INTEGER, completed_day TEXT, PRIMARY KEY(session,exercise));
                CREATE TABLE IF NOT EXISTS reviews (language TEXT, topic TEXT, due TEXT, level INTEGER, last_day TEXT,
                    PRIMARY KEY(language,topic));
                CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT);
                CREATE TABLE IF NOT EXISTS generated_history (fingerprint TEXT PRIMARY KEY, language TEXT,
                    topic TEXT, title TEXT, created TEXT);
            ''')
            if 'attempts' not in {row['name'] for row in db.execute('PRAGMA table_info(activity)')}:
                db.execute('ALTER TABLE activity ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0')
            db.execute('PRAGMA user_version=3')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def load_sessions(self):
        with self.connect() as db:
            return {row['id']: json.loads(row['payload']) for row in db.execute('SELECT * FROM sessions')}

    def save_session(self, key, payload):
        with self.connect() as db:
            db.execute('INSERT OR REPLACE INTO sessions VALUES (?,?,?)',
                       (key, json.dumps(payload, allow_nan=False), datetime.now().astimezone().isoformat()))
            for lesson in payload.get('lessons',[]):
                fingerprint=lesson.get('quality',{}).get('fingerprint')
                if fingerprint:
                    db.execute('INSERT OR IGNORE INTO generated_history VALUES (?,?,?,?,?)',
                               (fingerprint,lesson['language'],payload.get('topic',''),lesson['title'],datetime.now().astimezone().isoformat()))

    def recent_tasks(self, language, topic):
        with self.connect() as db:
            return [dict(row) for row in db.execute('SELECT fingerprint,title FROM generated_history WHERE language=? AND topic=? ORDER BY created DESC LIMIT 40',(language,topic))]

    def delete_session(self, key):
        with self.connect() as db:
            db.execute('DELETE FROM sessions WHERE id=?', (key,))

    def record(self, key, index, language, topic, passed, total):
        day = today()
        with self.connect() as db:
            previous = db.execute('SELECT completed_day,attempts FROM activity WHERE session=? AND exercise=?', (key,index)).fetchone()
            completed_day = previous['completed_day'] if previous else None
            first_pass = passed == total and not completed_day
            if first_pass:
                completed_day = day.isoformat()
            db.execute('INSERT OR REPLACE INTO activity VALUES (?,?,?,?,?,?,?,?)',
                       (key,index,language,topic,passed,total,completed_day,(previous['attempts'] if previous else 0)+1))
            old = db.execute('SELECT * FROM reviews WHERE language=? AND topic=?', (language,topic)).fetchone()
            # Re-running the same successful exercise must not inflate the review interval.
            if first_pass or passed < total:
                level = min(old['level'] + 1, 5) if old and first_pass and old['last_day'] != day.isoformat() else (old['level'] if old else 0)
                if passed < total:
                    level = 0
                interval = (1,3,7,14,30,60)[level]
                db.execute('INSERT OR REPLACE INTO reviews VALUES (?,?,?,?,?)',
                           (language,topic,(day+timedelta(days=interval)).isoformat(),level,day.isoformat()))

    def set_goal(self, value):
        if type(value) is not int or not 1 <= value <= 20:
            raise ValueError('Choose a daily goal of 1 to 20 completed exercises.')
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO settings VALUES ('goal',?)", (str(value),))

    def dashboard(self):
        with self.connect() as db:
            goal = db.execute("SELECT value FROM settings WHERE key='goal'").fetchone()
            rows = [dict(row) for row in db.execute('SELECT * FROM activity ORDER BY completed_day DESC')]
            reviews = [dict(row) for row in db.execute('SELECT * FROM reviews ORDER BY due, topic')]
        complete = [row for row in rows if row['completed_day']]
        days = {row['completed_day'] for row in complete}
        cursor = today() if today().isoformat() in days else today()-timedelta(days=1)
        streak = 0
        while cursor.isoformat() in days:
            streak += 1
            cursor -= timedelta(days=1)
        return {'goal': int(goal['value']) if goal else 1,
                'today_completed': sum(row['completed_day'] == today().isoformat() for row in complete),
                'streak': streak, 'total_completed': len(complete), 'history': rows[:50],
                'completed_topics': [{'language':language,'topic':topic} for language,topic in sorted({(row['language'],row['topic']) for row in complete})],
                'due': [row for row in reviews if row['due'] <= today().isoformat()],
                'reviews': reviews, 'paths': PATHS}

    def export(self):
        with self.connect() as db:
            activity = [dict(row) for row in db.execute('SELECT * FROM activity')]
        return {'format': 1, 'sessions': self.load_sessions(), 'progress': self.dashboard(),
                'activity': activity}

    def clear(self):
        with self.connect() as db:
            for table in ('sessions','activity','reviews','settings','generated_history'):
                db.execute('DELETE FROM '+table)
