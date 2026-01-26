"""
Secret Vault for encrypting sensitive data.
Uses Fernet symmetric encryption with a master key.
"""
import os
import logging
import threading
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

DEFAULT_KEY_FILE = Path("data/encryption.key")


class SecretVault:
    """
    Encrypts and decrypts secrets using Fernet.

    Usage:
        vault = SecretVault(key)
        encrypted = vault.encrypt("my-password")
        decrypted = vault.decrypt(encrypted)
    """

    def __init__(self, key: str):
        self.fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, value: str) -> str:
        """Encrypt a string. Empty strings are returned unchanged."""
        if not value:
            return ""
        return self.fernet.encrypt(value.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt a string. Empty strings are returned unchanged."""
        if not encrypted:
            return ""
        return self.fernet.decrypt(encrypted.encode()).decode()


def get_or_create_master_key(key_file: Optional[Path] = None) -> str:
    """Get master encryption key from env or file, create if needed."""
    env_key = os.environ.get("ENCRYPTION_KEY")
    if env_key:
        # Validate the key format
        try:
            Fernet(env_key.encode())
        except Exception as e:
            logger.error(f"Invalid ENCRYPTION_KEY format: {e}")
            raise ValueError("ENCRYPTION_KEY environment variable contains an invalid Fernet key")
        logger.debug("Using encryption key from ENCRYPTION_KEY env")
        return env_key

    if key_file is None:
        key_file = DEFAULT_KEY_FILE

    if key_file.exists():
        logger.debug(f"Loading encryption key from {key_file}")
        return key_file.read_text().strip()

    logger.info(f"Generating new encryption key, saving to {key_file}")
    key_file.parent.mkdir(parents=True, exist_ok=True)

    new_key = Fernet.generate_key().decode()
    key_file.write_text(new_key)
    key_file.chmod(0o600)

    return new_key


_vault: Optional[SecretVault] = None
_vault_lock = threading.Lock()


def get_vault() -> SecretVault:
    """Get or create global vault instance (thread-safe)."""
    global _vault
    if _vault is None:
        with _vault_lock:
            if _vault is None:  # Double-check locking
                key = get_or_create_master_key()
                _vault = SecretVault(key)
    return _vault
