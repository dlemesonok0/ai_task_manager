import pytest
from unittest.mock import patch, MagicMock
from fastapi import HTTPException
from services.auth_service import (
    verify_password,
    verify_access_token,
    create_access_token,
    authenticate_user,
    authenticate_user_record,
    register_user,
    require_auth,
    hash_password,
)


def test_verify_password_invalid_format():
    assert verify_password("pass", "invalid_hash") is False


def test_verify_password_wrong_algorithm():
    assert verify_password("pass", "bcrypt$salt$hash") is False


def test_verify_password_success():
    hashed = hash_password("testpass123", "testsalt")
    assert verify_password("testpass123", hashed) is True
    assert verify_password("wrongpass", hashed) is False


def test_verify_access_token_invalid_signature():
    token = "invalid.signature"
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_verify_access_token_invalid_json():
    import base64
    bad_payload = base64.urlsafe_b64encode(b"not-json").decode().rstrip("=")
    from services.auth_service import _sign
    signature = _sign(bad_payload)
    token = f"{bad_payload}.{signature}"
    with pytest.raises(HTTPException) as exc_info:
        verify_access_token(token)
    assert exc_info.value.status_code == 401


def test_verify_access_token_expired():
    with patch("services.auth_service.time.time", return_value=1000000):
        token = create_access_token("testuser", 1)
    with patch("services.auth_service.time.time", return_value=2000000):
        with pytest.raises(HTTPException) as exc_info:
            verify_access_token(token)
        assert exc_info.value.status_code == 401


def test_authenticate_user():
    with patch("services.auth_service.db_service") as mock_db:
        hashed = hash_password("testpass123", "salt")
        mock_db.get_user_by_username.return_value = {"username": "test", "password_hash": hashed}
        assert authenticate_user("test", "testpass123") is True
        assert authenticate_user("test", "wrong") is False


def test_authenticate_user_not_found():
    with patch("services.auth_service.db_service") as mock_db:
        mock_db.get_user_by_username.return_value = None
        assert authenticate_user("nobody", "pass") is False


def test_authenticate_user_record():
    with patch("services.auth_service.db_service") as mock_db:
        hashed = hash_password("testpass123", "salt")
        mock_db.get_user_by_username.return_value = {"id": 1, "username": "test", "password_hash": hashed}
        result = authenticate_user_record("test", "testpass123")
        assert result is not None
        assert result["id"] == 1


def test_authenticate_user_record_fail():
    with patch("services.auth_service.db_service") as mock_db:
        mock_db.get_user_by_username.return_value = None
        assert authenticate_user_record("nobody", "pass") is None


def test_register_user_duplicate():
    with patch("services.auth_service.db_service") as mock_db:
        mock_db.get_user_by_username.return_value = {"id": 1, "username": "existing"}
        with pytest.raises(HTTPException) as exc_info:
            register_user("existing", "password123")
        assert exc_info.value.status_code == 409


def test_require_auth_user_deleted():
    mock_creds = MagicMock()
    mock_creds.scheme = "Bearer"
    mock_creds.credentials = create_access_token("deleted_user", 999)
    with patch("services.auth_service.db_service") as mock_db:
        mock_db.get_user_by_id.return_value = None
        with pytest.raises(HTTPException) as exc_info:
            require_auth(mock_creds)
        assert exc_info.value.status_code == 401
