import sqlite3
from datetime import date, datetime

from dsutil.log import LocalLogger


class DatabaseHelper:
    """Helper class for database access."""

    def __init__(self):
        self.logger = LocalLogger.setup_logger(self.__class__.__name__)
        self.db_file = "bug_zapper_scores.db"

    def init_db(self):
        """Initialize the database."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_scores
            (date TEXT PRIMARY KEY, score INTEGER)
            """)
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS kills
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT,
                hour INTEGER)
            """)
            conn.commit()

    def update_score(self):
        """Update the score."""
        today = date.today().isoformat()
        now = datetime.now()
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
            INSERT INTO daily_scores (date, score) VALUES (?, 1)
            ON CONFLICT(date) DO UPDATE SET score = score + 1
            """,
                (today,),
            )
            cursor.execute(
                """
            INSERT INTO kills (timestamp, hour) VALUES (?, ?)
            """,
                (now.isoformat(), now.hour),
            )
            conn.commit()

    def get_daily_score(self):
        """Get today's daily score."""
        today = date.today().isoformat()
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT score FROM daily_scores WHERE date = ?", (today,))
            result = cursor.fetchone()
            return result[0] if result else 0

    def display_scores(self):
        """Display scores."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()

            # Daily scores
            cursor.execute("SELECT date, score FROM daily_scores ORDER BY date DESC LIMIT 7")
            results = cursor.fetchall()

            self.logger.info("Recent Bug Zapping Scores:")
            for row in results:
                self.logger.info(f"{row[0]}: {row[1]} kills")

            # All-time high score
            cursor.execute("SELECT MAX(score), date FROM daily_scores")
            max_score, max_date = cursor.fetchone()
            self.logger.info(f"All-time high score: {max_score} kills on {max_date}")

            # Average daily kills
            cursor.execute("SELECT AVG(score) FROM daily_scores")
            avg_score = cursor.fetchone()[0]
            self.logger.info(f"Average daily kills: {avg_score:.2f}")

            # Busiest hour
            cursor.execute("""
            SELECT hour, COUNT(*) as kill_count
            FROM kills
            GROUP BY hour
            ORDER BY kill_count DESC
            LIMIT 1
            """)
            busiest_hour, kill_count = cursor.fetchone()
            self.logger.info(f"Busiest hour: {busiest_hour}:00 with {kill_count} kills")

    def get_hourly_distribution(self):
        """Get hourly distribution."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT hour, COUNT(*) as kill_count
            FROM kills
            GROUP BY hour
            ORDER BY hour
            """)
            return cursor.fetchall()

    def display_hourly_distribution(self):
        """Display hourly distribution."""
        distribution = self.get_hourly_distribution()
        self.logger.info("Hourly Kill Distribution:")
        for hour, count in distribution:
            self.logger.info(f"{hour:02d}:00 - {count} kills")
