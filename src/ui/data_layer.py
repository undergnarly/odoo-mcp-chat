"""
Data layer for Chainlit chat history persistence using SQLite
"""
import hashlib
import os
import secrets
from pathlib import Path
from typing import Optional, Tuple

from chainlit.data.sql_alchemy import SQLAlchemyDataLayer

from src.config import get_settings
from src.utils.logging import get_logger

logger = get_logger(__name__)


def hash_password(password: str, salt: Optional[str] = None) -> Tuple[str, str]:
    """Hash a password with salt using SHA256"""
    if salt is None:
        salt = secrets.token_hex(16)
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}", salt


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against stored hash"""
    try:
        salt, _ = stored_hash.split(":")
        new_hash, _ = hash_password(password, salt)
        return new_hash == stored_hash
    except (ValueError, AttributeError):
        return False


async def register_user(username: str, password: str, email: Optional[str] = None) -> bool:
    """Register a new user"""
    import aiosqlite

    db_path = get_database_path()
    password_hash, _ = hash_password(password)

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            await db.execute(
                'INSERT INTO app_users (username, password_hash, email) VALUES (?, ?, ?)',
                (username, password_hash, email)
            )
            await db.commit()
            logger.info(f"User registered: {username}")
            return True
    except Exception as e:
        logger.error(f"Failed to register user {username}: {e}")
        return False


async def authenticate_user(username: str, password: str) -> bool:
    """Authenticate a user"""
    import aiosqlite

    db_path = get_database_path()

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute(
                'SELECT password_hash, is_active FROM app_users WHERE username = ?',
                (username,)
            )
            row = await cursor.fetchone()

            if row and row[1]:  # Check if user exists and is active
                return verify_password(password, row[0])
            return False
    except Exception as e:
        logger.error(f"Failed to authenticate user {username}: {e}")
        return False


async def user_exists(username: str) -> bool:
    """Check if a user exists"""
    import aiosqlite

    db_path = get_database_path()

    try:
        async with aiosqlite.connect(str(db_path)) as db:
            cursor = await db.execute(
                'SELECT 1 FROM app_users WHERE username = ?',
                (username,)
            )
            row = await cursor.fetchone()
            return row is not None
    except Exception as e:
        logger.error(f"Failed to check user existence: {e}")
        return False


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

-- App users table for registration
CREATE TABLE IF NOT EXISTS app_users (
    "id" INTEGER PRIMARY KEY AUTOINCREMENT,
    "username" TEXT NOT NULL UNIQUE,
    "password_hash" TEXT NOT NULL,
    "email" TEXT,
    "created_at" TEXT DEFAULT CURRENT_TIMESTAMP,
    "is_active" INTEGER DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_app_users_username ON app_users("username");
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
