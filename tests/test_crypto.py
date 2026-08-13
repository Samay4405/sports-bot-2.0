"""Crypto round-trip tests — verify AES-256-GCM encrypt/decrypt works correctly."""

from app.security.crypto import decrypt, encrypt, generate_key


def test_encrypt_decrypt_roundtrip():
    """Encrypting then decrypting should return the original plaintext."""
    key = bytes.fromhex(generate_key())
    original = "test_user@mitwpu.edu.in"

    encrypted = encrypt(original, key)
    decrypted = decrypt(encrypted, key)

    assert decrypted == original


def test_encrypted_format():
    """Encrypted output should be in 'nonce:ciphertext:tag' hex format."""
    key = bytes.fromhex(generate_key())
    encrypted = encrypt("hello", key)

    parts = encrypted.split(":")
    assert len(parts) == 3, f"Expected 3 parts, got {len(parts)}"

    # Nonce should be 12 bytes = 24 hex chars
    assert len(parts[0]) == 24, f"Nonce should be 24 hex chars, got {len(parts[0])}"
    # Tag should be 16 bytes = 32 hex chars
    assert len(parts[2]) == 32, f"Tag should be 32 hex chars, got {len(parts[2])}"


def test_unique_nonces():
    """Each encryption should produce a different ciphertext (unique nonce)."""
    key = bytes.fromhex(generate_key())
    plaintext = "same_password"

    encrypted1 = encrypt(plaintext, key)
    encrypted2 = encrypt(plaintext, key)

    assert encrypted1 != encrypted2, "Two encryptions of the same text should differ"

    # But both should decrypt to the same value
    assert decrypt(encrypted1, key) == plaintext
    assert decrypt(encrypted2, key) == plaintext


def test_wrong_key_fails():
    """Decrypting with the wrong key should raise an error."""
    key1 = bytes.fromhex(generate_key())
    key2 = bytes.fromhex(generate_key())

    encrypted = encrypt("secret", key1)

    try:
        decrypt(encrypted, key2)
        assert False, "Should have raised an error"
    except Exception:
        pass  # Expected — wrong key should fail


def test_empty_string():
    """Should handle encrypting empty strings."""
    key = bytes.fromhex(generate_key())
    encrypted = encrypt("", key)
    assert decrypt(encrypted, key) == ""


def test_unicode_content():
    """Should handle Unicode characters (names, special chars)."""
    key = bytes.fromhex(generate_key())
    original = "Sämay@mütwpu.edu.in 🏊‍♂️"
    encrypted = encrypt(original, key)
    assert decrypt(encrypted, key) == original
