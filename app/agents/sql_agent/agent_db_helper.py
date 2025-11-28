from dotenv import load_dotenv
import psycopg2
import os
import logging

load_dotenv()

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Get Postgres connection info from environment or prompt
PG_HOST = os.getenv("PG_HOST", "localhost")
PG_PORT = os.getenv("PG_PORT", "5555")
PG_USER = os.getenv("PG_USER", "dev")
PG_PASSWORD = os.getenv("PG_PASSWORD", "dev")
PG_URL = os.getenv("PG_URL", "")


def get_db_connection(database: str | None = None):
    """Create a direct database connection."""
    try:
        if PG_URL:
            # Parse PG_URL if needed
            conn = psycopg2.connect(PG_URL)
        else:
            conn = psycopg2.connect(
                host=PG_HOST,
                port=PG_PORT,
                database=database,
                user=PG_USER,
                password=PG_PASSWORD,
            )
        return conn
    except Exception as e:
        logger.error(f"Error connecting to {database}: {e}")
        return None
