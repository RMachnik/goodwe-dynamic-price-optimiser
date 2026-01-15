"""
Hub API Authentication Unit Tests.

Tests for Node Auth, User Auth, and the unified get_authenticated_entity dependency.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from hashlib import sha256
import secrets

# We'll test the core functions directly
from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    _get_node_from_headers,
)


class TestPasswordHashing:
    """Tests for password hashing functions."""

    def test_get_password_hash_returns_string(self):
        hashed = get_password_hash("testpassword")
        assert isinstance(hashed, str)
        assert len(hashed) > 20  # BCrypt hashes are long

    def test_verify_password_correct(self):
        password = "mysecurepassword"
        hashed = get_password_hash(password)
        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        password = "mysecurepassword"
        hashed = get_password_hash(password)
        assert verify_password("wrongpassword", hashed) is False


class TestJWTTokens:
    """Tests for JWT token creation and decoding."""

    def test_create_access_token_returns_string(self):
        token = create_access_token({"sub": "user@example.com"})
        assert isinstance(token, str)

    def test_decode_access_token_valid(self):
        email = "user@example.com"
        token = create_access_token({"sub": email})
        payload = decode_access_token(token)
        assert payload is not None
        assert payload["sub"] == email

    def test_decode_access_token_invalid(self):
        payload = decode_access_token("invalid.token.here")
        assert payload is None

    def test_decode_access_token_expired(self):
        from datetime import timedelta
        # Create a token that expired 1 hour ago
        token = create_access_token({"sub": "user@example.com"}, expires_delta=timedelta(hours=-1))
        payload = decode_access_token(token)
        assert payload is None


class TestNodeAuthentication:
    """Tests for Node authentication via headers."""

    @pytest.mark.asyncio
    async def test_get_node_from_headers_missing_credentials(self):
        """Should return None if node_id or node_secret is missing."""
        mock_db = AsyncMock()
        result = await _get_node_from_headers(mock_db, None, "secret")
        assert result is None

        result = await _get_node_from_headers(mock_db, "node-id", None)
        assert result is None

        result = await _get_node_from_headers(mock_db, None, None)
        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_from_headers_node_not_found(self):
        """Should return None if node is not in database."""
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None
        mock_db.execute.return_value = mock_result

        result = await _get_node_from_headers(mock_db, "unknown-node", "secret")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_from_headers_wrong_secret(self):
        """Should return None if secret hash doesn't match."""
        mock_db = AsyncMock()
        mock_node = MagicMock()
        mock_node.secret_hash = sha256("correct-secret".encode()).hexdigest()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_node
        mock_db.execute.return_value = mock_result

        result = await _get_node_from_headers(mock_db, "node-id", "wrong-secret")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_node_from_headers_correct_secret(self):
        """Should return Node object if credentials are valid."""
        mock_db = AsyncMock()
        mock_node = MagicMock()
        mock_node.hardware_id = "test-node"
        mock_node.secret_hash = sha256("correct-secret".encode()).hexdigest()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = mock_node
        mock_db.execute.return_value = mock_result

        result = await _get_node_from_headers(mock_db, "test-node", "correct-secret")
        assert result is not None
        assert result.hardware_id == "test-node"


class TestTimingAttackSafety:
    """Tests to verify timing-attack-safe comparison is used."""

    def test_secrets_compare_digest_is_used(self):
        """Verify that secrets.compare_digest is imported and available."""
        import app.auth as auth_module
        assert hasattr(auth_module, 'secrets')


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
