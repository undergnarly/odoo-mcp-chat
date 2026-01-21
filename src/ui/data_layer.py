"""
Data layer for Chainlit chat history persistence using SQLite
"""
import os
from pathlib import Path
from typing import Optional

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


# SQL schema for Chainlit tables
CHAINLIT_SCHEMA = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    "id" TEXT PRIMARY KEY,
    "identifier" TEXT NOT NULL UNIQUE,
    "metadata" TEXT DEFAULT '{}',
    "createdAt" TEXT
);

-- Threads table
CREATE TABLE IF NOT EXISTS threads (
    "id" TEXT PRIMARY KEY,
    "createdAt" TEXT,
    "name" TEXT,
    "userId" TEXT,
    "userIdentifier" TEXT,
    "tags" TEXT,
    "metadata" TEXT,
    FOREIGN KEY ("userId") REFERENCES users("id")
);

-- Steps table
CREATE TABLE IF NOT EXISTS steps (
    "id" TEXT PRIMARY KEY,
    "name" TEXT,
    "type" TEXT,
    "threadId" TEXT,
    "parentId" TEXT,
    "streaming" INTEGER,
    "waitForAnswer" INTEGER,
    "isError" INTEGER,
    "metadata" TEXT DEFAULT '{}',
    "tags" TEXT,
    "input" TEXT,
    "output" TEXT,
    "createdAt" TEXT,
    "start" TEXT,
    "end" TEXT,
    "generation" TEXT DEFAULT '{}',
    "showInput" TEXT,
    "language" TEXT,
    FOREIGN KEY ("threadId") REFERENCES threads("id")
);

-- Feedbacks table
CREATE TABLE IF NOT EXISTS feedbacks (
    "id" TEXT PRIMARY KEY,
    "forId" TEXT,
    "threadId" TEXT,
    "value" INTEGER,
    "comment" TEXT,
    FOREIGN KEY ("forId") REFERENCES steps("id")
);

-- Elements table (for file attachments)
CREATE TABLE IF NOT EXISTS elements (
    "id" TEXT PRIMARY KEY,
    "threadId" TEXT,
    "type" TEXT,
    "chainlitKey" TEXT,
    "url" TEXT,
    "objectKey" TEXT,
    "name" TEXT,
    "display" TEXT,
    "size" TEXT,
    "language" TEXT,
    "page" INTEGER,
    "autoPlay" INTEGER,
    "playerConfig" TEXT,
    "forId" TEXT,
    "mime" TEXT,
    "props" TEXT DEFAULT '{}',
    FOREIGN KEY ("threadId") REFERENCES threads("id")
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_threads_userid ON threads("userId");
CREATE INDEX IF NOT EXISTS idx_threads_createdat ON threads("createdAt");
CREATE INDEX IF NOT EXISTS idx_steps_threadid ON steps("threadId");
CREATE INDEX IF NOT EXISTS idx_steps_createdat ON steps("createdAt");
CREATE INDEX IF NOT EXISTS idx_feedbacks_forid ON feedbacks("forId");
CREATE INDEX IF NOT EXISTS idx_elements_threadid ON elements("threadId");
"""


def get_database_path() -> Path:
    """Get the path to the SQLite database file"""
    settings = get_settings()
    # Store database in the same directory as logs
    db_dir = settings.logs_dir
    db_dir.mkdir(parents=True, exist_ok=True)
    return db_dir / "chat_history.db"


def get_database_url() -> str:
    """Get the SQLAlchemy connection URL for SQLite"""
    db_path = get_database_path()
    # Use aiosqlite for async SQLite support
    return f"sqlite+aiosqlite:///{db_path}"


async def init_database():
    """Initialize the database schema"""
    import aiosqlite

    db_path = get_database_path()
    logger.info(f"Initializing chat history database at: {db_path}")

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            # Execute schema creation
            await db.executescript(CHAINLIT_SCHEMA)
            await db.commit()
            logger.info("Database schema initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database schema: {e}")
        raise


def create_data_layer() -> Optional[SQLAlchemyDataLayer]:
    """Create and return a SQLAlchemy data layer instance"""
    try:
        db_url = get_database_url()
        logger.info(f"Creating data layer with URL: {db_url}")

        data_layer = SQLAlchemyDataLayer(
            conninfo=db_url,
            user_thread_limit=100,
            show_logger=True,
        )

        logger.info("SQLAlchemy data layer created successfully")
        return data_layer

    except Exception as e:
        logger.error(f"Failed to create data layer: {e}")
        return None
