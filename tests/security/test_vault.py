"""Tests for SecretVault encryption."""
import pytest
from pathlib import Path


class TestSecretVault:
    """Test SecretVault encryption/decryption."""

    def test_encrypt_decrypt_roundtrip(self, tmp_path):
        """Encrypted value can be decrypted back."""
        from src.security.vault import SecretVault, get_or_create_master_key

        key_file = tmp_path / "test.key"
        key = get_or_create_master_key(key_file=key_file)
        vault = SecretVault(key)

        original = "my-secret-password-123"
        encrypted = vault.encrypt(original)
        decrypted = vault.decrypt(encrypted)

        assert decrypted == original
        assert encrypted != original

    def test_encrypted_value_is_different_each_time(self, tmp_path):
        """Same value produces different ciphertext (IV)."""
        from src.security.vault import SecretVault, get_or_create_master_key

        key_file = tmp_path / "test.key"
        key = get_or_create_master_key(key_file=key_file)
        vault = SecretVault(key)

        value = "same-secret"
        encrypted1 = vault.encrypt(value)
        encrypted2 = vault.encrypt(value)

        assert encrypted1 != encrypted2

    def test_get_or_create_master_key_creates_file(self, tmp_path, monkeypatch):
        """Key file is created if not exists."""
        from src.security.vault import get_or_create_master_key

        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        key_file = tmp_path / "new.key"
        assert not key_file.exists()

        key = get_or_create_master_key(key_file=key_file)

        assert key_file.exists()
        assert len(key) == 44  # Fernet key is 32 bytes base64 = 44 chars

    def test_get_or_create_master_key_reuses_existing(self, tmp_path, monkeypatch):
        """Existing key file is reused."""
        from src.security.vault import get_or_create_master_key

        monkeypatch.delenv("ENCRYPTION_KEY", raising=False)

        key_file = tmp_path / "existing.key"
        key1 = get_or_create_master_key(key_file=key_file)
        key2 = get_or_create_master_key(key_file=key_file)

        assert key1 == key2

    def test_get_or_create_master_key_from_env(self, tmp_path, monkeypatch):
        """Key from environment variable takes priority."""
        from cryptography.fernet import Fernet
        from src.security.vault import get_or_create_master_key

        env_key = Fernet.generate_key().decode()
        monkeypatch.setenv("ENCRYPTION_KEY", env_key)

        key_file = tmp_path / "ignored.key"
        key = get_or_create_master_key(key_file=key_file)

        assert key == env_key
        assert not key_file.exists()
