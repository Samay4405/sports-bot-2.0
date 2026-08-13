"""AES-256-GCM encryption/decryption for credential storage.

Encrypts usernames and passwords at rest in the database. Each value
gets a unique random nonce (IV), and the ciphertext includes an
authentication tag to prevent tampering.

Storage format (hex-encoded):
    {nonce_hex}:{ciphertext_hex}:{tag_hex}

This format is chosen for readability and easy debugging. The nonce is
12 bytes (96 bits), which is the recommended size for GCM.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


def encrypt(plaintext: str, key: bytes) -> str:
    """Encrypt a plaintext string using AES-256-GCM.

    Args:
        plaintext: The string to encrypt.
        key: 32-byte encryption key.

    Returns:
        Hex-encoded string in format "nonce:ciphertext:tag"

    Raises:
        ValueError: If the key is not exactly 32 bytes.
    """
    if len(key) != 32:
        raise ValueError(f"Key must be 32 bytes, got {len(key)}")

    nonce = os.urandom(12)  # 96-bit nonce (recommended for GCM)
    aesgcm = AESGCM(key)

    # AESGCM.encrypt appends the 16-byte tag to the ciphertext
    ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Split ciphertext and tag (tag is always last 16 bytes)
    ciphertext = ciphertext_with_tag[:-16]
    tag = ciphertext_with_tag[-16:]

    return f"{nonce.hex()}:{ciphertext.hex()}:{tag.hex()}"


def decrypt(encrypted: str, key: bytes) -> str:
    """Decrypt an AES-256-GCM encrypted string.

    Args:
        encrypted: Hex-encoded string in format "nonce:ciphertext:tag"
        key: 32-byte encryption key (must match the key used to encrypt).

    Returns:
        The original plaintext string.

    Raises:
        ValueError: If the encrypted string format is invalid or key is wrong.
        cryptography.exceptions.InvalidTag: If the ciphertext has been tampered with.
    """
    if len(key) != 32:
        raise ValueError(f"Key must be 32 bytes, got {len(key)}")

    parts = encrypted.split(":")
    if len(parts) != 3:
        raise ValueError(
            f"Invalid encrypted format: expected 'nonce:ciphertext:tag', got {len(parts)} parts"
        )

    nonce = bytes.fromhex(parts[0])
    ciphertext = bytes.fromhex(parts[1])
    tag = bytes.fromhex(parts[2])

    aesgcm = AESGCM(key)

    # AESGCM.decrypt expects ciphertext + tag concatenated
    plaintext_bytes = aesgcm.decrypt(nonce, ciphertext + tag, None)

    return plaintext_bytes.decode("utf-8")


def generate_key() -> str:
    """Generate a new random 32-byte encryption key.

    Returns:
        64-character hex string suitable for ENCRYPTION_KEY env var.
    """
    return os.urandom(32).hex()
