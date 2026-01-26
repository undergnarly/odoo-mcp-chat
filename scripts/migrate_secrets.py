#!/usr/bin/env python3
"""
Migrate existing plain-text secrets to encrypted format.
Run this once after deploying the encryption feature.
"""
import sys
import os
import sqlite3
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.security.vault import get_vault
from src.settings_manager.settings_db import SECRET_KEYS, get_db_path


def is_encrypted(value: str) -> bool:
    """Check if value looks like it's already encrypted."""
    if not value:
        return False
    # Fernet tokens start with 'gAAAAA'
    return value.startswith("gAAAAA")


def migrate_secrets():
    """Migrate plain-text secrets to encrypted format."""
    db_path = get_db_path()

    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return

    vault = get_vault()
    migrated = 0
    skipped = 0

    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    # Check if settings table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='settings'")
    if not cursor.fetchone():
        print("Settings table does not exist yet. Nothing to migrate.")
        conn.close()
        return

    for key in SECRET_KEYS:
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()

        if not row or not row[0]:
            print(f"  {key}: not set, skipping")
            skipped += 1
            continue

        value = row[0]

        if is_encrypted(value):
            print(f"  {key}: already encrypted, skipping")
            skipped += 1
            continue

        # Encrypt the value
        encrypted = vault.encrypt(value)
        cursor.execute("UPDATE settings SET value = ? WHERE key = ?", (encrypted, key))
        print(f"  {key}: encrypted successfully")
        migrated += 1

    conn.commit()
    conn.close()

    print(f"\nMigration complete: {migrated} encrypted, {skipped} skipped")


if __name__ == "__main__":
    print("Secrets Migration Script")
    print("=" * 40)
    print()
    migrate_secrets()
