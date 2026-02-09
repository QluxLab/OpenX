"""
Tests for authentication endpoints.
"""
import pytest


class TestAuthRegistration:
    """Tests for user registration."""

    def test_register_new_user(self, db_session, client_factory):
        """Test successful user registration."""
        client = client_factory(db_session)
        response = client.post(
            "/api/auth/new",
            json={"username": "newuser"}
        )

        assert response.status_code == 200
        data = response.json()
        assert "sk" in data
        assert "rk" in data
        assert data["sk"].startswith("sk-")
        assert data["rk"].startswith("rk-")

    def test_register_duplicate_username(self, db_session, client_factory, test_user_data):
        """Test that duplicate usernames are rejected."""
        client = client_factory(db_session)
        response = client.post(
            "/api/auth/new",
            json={"username": test_user_data["username"]}
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"].lower()

    def test_register_short_username(self, db_session, client_factory):
        """Test that short usernames are rejected."""
        client = client_factory(db_session)
        response = client.post(
            "/api/auth/new",
            json={"username": "ab"}
        )

        assert response.status_code == 422  # Validation error


class TestAuthRecovery:
    """Tests for key recovery."""

    def test_recovery_valid_keys(self, db_session, client_factory, test_user_data):
        """Test successful key recovery with valid keys."""
        client = client_factory(db_session)
        response = client.post(
            "/api/auth/recovery",
            json={
                "sk": test_user_data["sk"],
                "rk": test_user_data["rk"]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "sk" in data
        assert "rk" in data
        # New secret key should be different
        assert data["sk"] != test_user_data["sk"]
        # Recovery key stays the same
        assert data["rk"] == test_user_data["rk"]

    def test_recovery_invalid_secret_key(self, db_session, client_factory, test_user_data):
        """Test recovery with invalid secret key."""
        client = client_factory(db_session)
        response = client.post(
            "/api/auth/recovery",
            json={
                "sk": "sk-invalidkey12345678",
                "rk": test_user_data["rk"]
            }
        )

        assert response.status_code == 401

    def test_recovery_invalid_recovery_key(self, db_session, client_factory, test_user_data):
        """Test recovery with invalid recovery key."""
        client = client_factory(db_session)
        response = client.post(
            "/api/auth/recovery",
            json={
                "sk": test_user_data["sk"],
                "rk": "rk-invalidkey12345678901234567890123"
            }
        )

        assert response.status_code == 401
