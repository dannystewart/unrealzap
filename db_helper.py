import json
import sqlite3
import threading
from datetime import date, datetime, timedelta

from dsutil.log import LocalLogger
import signal
import time


class DatabaseHelper:
    """Helper class for database access."""

    def __init__(self, db_file="bug_zapper.db"):
        self.logger = LocalLogger.setup_logger(self.__class__.__name__)
        self.db_file = db_file
        self.lock = threading.Lock()
        self.init_db()

    def get_connection(self):
        """Get a new database connection."""
        return sqlite3.connect(self.db_file)

    def init_db(self):
        """Initialize the database with optimized schema."""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS audio_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    duration REAL,
                    dominant_frequency REAL,
                    high_energy_ratio REAL,
                    peak_amplitude REAL,
                    is_zap BOOLEAN,
                    audio_features TEXT
                )
                """)
                cursor.execute(
                    "CREATE INDEX IF NOT EXISTS idx_timestamp ON audio_events(timestamp)"
                )
                conn.commit()

    def record_audio_event(
        self,
        duration,
        dominant_frequency,
        high_energy_ratio,
        peak_amplitude,
        audio_features,
        is_zap=None,
    ):
        """Record an audio event, with potential zap detection."""
        timestamp = datetime.now().isoformat()

        if self.might_be_zap(duration, dominant_frequency, high_energy_ratio):
            with self.lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                    INSERT INTO audio_events
                    (timestamp, duration, dominant_frequency, high_energy_ratio, peak_amplitude, is_zap, audio_features)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            timestamp,
                            duration,
                            dominant_frequency,
                            high_energy_ratio,
                            peak_amplitude,
                            is_zap,
                            json.dumps(audio_features),
                        ),
                    )
                    conn.commit()

    def might_be_zap(self, duration, dominant_frequency, high_energy_ratio):
        """Determine if an event might be a zap based on basic criteria."""
        return duration < 0.1 and dominant_frequency > 5000 and high_energy_ratio > 0.5

    def get_recent_events(self, limit=10):
        """Get recent audio events."""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                SELECT * FROM audio_events
                WHERE timestamp > ?
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                    (datetime.now() - timedelta(days=7), limit),
                )
                return cursor.fetchall()

    def get_zap_statistics(self):
        """Get statistics about zap events from the last 30 days."""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                SELECT
                    AVG(duration) as avg_duration,
                    AVG(dominant_frequency) as avg_frequency,
                    AVG(high_energy_ratio) as avg_energy_ratio,
                    AVG(peak_amplitude) as avg_amplitude
                FROM audio_events
                WHERE is_zap = 1 AND timestamp > ?
                """,
                    (datetime.now() - timedelta(days=30),),
                )
                return cursor.fetchone()

    def get_database_size(self):
        """Get the current size of the database file in MB."""
        import os

        return os.path.getsize(self.db_file) / (1024 * 1024)

    def one_time_cleanup(self, batch_size=1000):  # noqa: ARG002
        """Perform a one-time cleanup of the database to reduce its size, with progress reporting and safe interruption."""
        print("Starting one-time cleanup...")
        start_time = time.time()

        # Set up signal handling for safe interruption
        original_sigint_handler = signal.getsignal(signal.SIGINT)
        original_sigterm_handler = signal.getsignal(signal.SIGTERM)
        cleanup_interrupted = False

        def signal_handler(signum, frame):  # noqa: ARG001
            nonlocal cleanup_interrupted
            cleanup_interrupted = True
            print("\nCleanup interrupted. Finishing current operation and exiting...")

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            with self.lock:
                with self.get_connection() as conn:
                    cursor = conn.cursor()

                    # Get the total number of events
                    cursor.execute("SELECT COUNT(*) FROM audio_events")
                    total_events = cursor.fetchone()[0]

                    # If we have more than 10,000 events, keep only the latest 10,000
                    if total_events > 10000:
                        cursor.execute("""
                        DELETE FROM audio_events
                        WHERE id NOT IN (
                            SELECT id
                            FROM audio_events
                            ORDER BY timestamp DESC
                            LIMIT 10000
                        )
                        """)

                    # Aggregate old data
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS hourly_aggregates (
                        hour TEXT PRIMARY KEY,
                        avg_duration REAL,
                        avg_dominant_frequency REAL,
                        avg_high_energy_ratio REAL,
                        avg_peak_amplitude REAL,
                        zap_count INTEGER
                    )
                    """)

                    cursor.execute("""
                    INSERT OR REPLACE INTO hourly_aggregates
                    SELECT
                        strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                        AVG(duration) as avg_duration,
                        AVG(dominant_frequency) as avg_dominant_frequency,
                        AVG(high_energy_ratio) as avg_high_energy_ratio,
                        AVG(peak_amplitude) as avg_peak_amplitude,
                        SUM(CASE WHEN is_zap = 1 THEN 1 ELSE 0 END) as zap_count
                    FROM audio_events
                    WHERE timestamp < datetime('now', '-1 day')
                    GROUP BY hour
                    """)

                    # Remove aggregated data from the main table
                    cursor.execute("""
                    DELETE FROM audio_events
                    WHERE timestamp < datetime('now', '-1 day')
                    """)

                    conn.commit()

                # Check for interruption after each major operation
                if cleanup_interrupted:
                    print("Cleanup interrupted. Rolling back changes...")
                    conn.rollback()
                    return

                conn.commit()

            # Only optimize if not interrupted
            if not cleanup_interrupted:
                print("Optimizing database...")
                self.optimize_database()

        finally:
            # Restore original signal handlers
            signal.signal(signal.SIGINT, original_sigint_handler)
            signal.signal(signal.SIGTERM, original_sigterm_handler)

        end_time = time.time()
        print(
            f"One-time cleanup {'completed' if not cleanup_interrupted else 'interrupted'} after {end_time - start_time:.2f} seconds."
        )

    def cleanup_old_data(self):
        """Remove data older than 30 days."""
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM audio_events WHERE timestamp < ?",
                    (datetime.now() - timedelta(days=30),),
                )
                conn.commit()

    def optimize_database(self):
        """Optimize the database to reduce its size."""
        with self.lock:
            with self.get_connection() as conn:
                conn.execute("VACUUM")

    def maintain_database(self):
        """Perform regular database maintenance."""
        with self.lock:
            self.cleanup_old_data()
            self.aggregate_hourly_data()
            self.optimize_database()

    def aggregate_hourly_data(self):
        """Aggregate hourly data to reduce database size."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS hourly_aggregates (
                hour TEXT PRIMARY KEY,
                avg_duration REAL,
                avg_dominant_frequency REAL,
                avg_high_energy_ratio REAL,
                avg_peak_amplitude REAL,
                zap_count INTEGER
            )
            """)

            # Aggregate data by hour
            cursor.execute("""
            INSERT OR REPLACE INTO hourly_aggregates
            SELECT
                strftime('%Y-%m-%d %H:00:00', timestamp) as hour,
                AVG(duration) as avg_duration,
                AVG(dominant_frequency) as avg_dominant_frequency,
                AVG(high_energy_ratio) as avg_high_energy_ratio,
                AVG(peak_amplitude) as avg_peak_amplitude,
                SUM(CASE WHEN is_zap = 1 THEN 1 ELSE 0 END) as zap_count
            FROM audio_events
            WHERE timestamp < datetime('now', '-1 hour')
            GROUP BY hour
            """)

            # Remove aggregated data from the main table
            cursor.execute("""
            DELETE FROM audio_events
            WHERE timestamp < datetime('now', '-1 hour')
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
