import os
import smtplib
from unittest.mock import MagicMock, patch
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core import mailer
from app.core.mailer import (
    get_mailer_config,
    is_smtp_configured,
    build_otp_email_message,
    send_otp_email,
)

client = TestClient(app)

def test_is_smtp_configured_false_when_empty(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    assert is_smtp_configured() is False

def test_is_smtp_configured_true_when_host_set(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    assert is_smtp_configured() is True

def test_get_mailer_config_defaults_and_parsing(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "  smtp.example.com  ")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret123")
    monkeypatch.setenv("EMAILS_FROM_EMAIL", "custom@example.com")

    cfg = get_mailer_config()
    assert cfg["host"] == "smtp.example.com"
    assert cfg["port"] == 465
    assert cfg["user"] == "user@example.com"
    assert cfg["password"] == "secret123"
    assert cfg["from_email"] == "custom@example.com"

def test_get_mailer_config_fallback_port(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "not-a-number")
    cfg = get_mailer_config()
    assert cfg["port"] == 587

def test_build_otp_email_message_structure(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("EMAILS_FROM_EMAIL", "sender@passkhadam.org")

    msg = build_otp_email_message(
        to_email="recipient@test.org",
        otp_code="849201"
    )

    assert msg["To"] == "recipient@test.org"
    assert "PassKhadam Identity" in msg["From"]
    assert "sender@passkhadam.org" in msg["From"]
    assert "PASSKHADAM" in msg["Subject"]

    payload = msg.get_payload()
    assert len(payload) == 2
    plain_part, html_part = payload[0], payload[1]

    plain_text = plain_part.get_payload(decode=True).decode("utf-8")
    assert "849201" in plain_text
    assert "5 minutes" in plain_text

    html_text = html_part.get_payload(decode=True).decode("utf-8")
    assert "849201" in html_text
    assert "PASSKHADAM" in html_text
    assert "border-radius" in html_text

def test_send_otp_email_unconfigured_host(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "")
    success, err = send_otp_email("recipient@test.org", "123456")
    assert success is False
    assert "not configured" in err.lower()

@patch("app.core.mailer.smtplib.SMTP")
def test_send_otp_email_smtp_starttls_success(mock_smtp_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "mailer@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app_pwd_123")

    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    success, err = send_otp_email("worker@passkhadam.org", "729415")

    assert success is True
    assert err is None
    mock_smtp_cls.assert_called_once_with("smtp.gmail.com", 587, timeout=10)
    mock_server.starttls.assert_called_once()
    mock_server.login.assert_called_once_with("mailer@gmail.com", "app_pwd_123")
    mock_server.send_message.assert_called_once()

@patch("app.core.mailer.smtplib.SMTP_SSL")
def test_send_otp_email_smtp_ssl_success(mock_smtp_ssl_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "mailer@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app_pwd_123")

    mock_server = MagicMock()
    mock_smtp_ssl_cls.return_value.__enter__.return_value = mock_server

    success, err = send_otp_email("worker@passkhadam.org", "729415")

    assert success is True
    assert err is None
    mock_smtp_ssl_cls.assert_called_once()
    mock_server.login.assert_called_once_with("mailer@gmail.com", "app_pwd_123")
    mock_server.send_message.assert_called_once()

@patch("app.core.mailer.smtplib.SMTP")
def test_send_otp_email_auth_failure(mock_smtp_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "mailer@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "wrong_password")

    mock_server = MagicMock()
    mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication failed")
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    success, err = send_otp_email("worker@passkhadam.org", "729415")

    assert success is False
    assert "authentication failed" in err.lower()

@patch("app.core.mailer.is_smtp_configured")
@patch("app.core.mailer.send_otp_email")
def test_send_email_otp_endpoint_with_smtp_success(mock_send, mock_is_configured):
    mock_is_configured.return_value = True
    mock_send.return_value = (True, None)

    resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "live.recipient@example.com"}
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["delivery_mode"] == "smtp"
    assert "Real verification email" in data["message"]
    assert "live.recipient@example.com" in data["email"]
    assert data["simulated_email"]["to"] == "live.recipient@example.com"

@patch("app.core.mailer.is_smtp_configured")
@patch("app.core.mailer.send_otp_email")
def test_send_email_otp_endpoint_with_smtp_error_fallback(mock_send, mock_is_configured):
    mock_is_configured.return_value = True
    mock_send.return_value = (False, "Connection refused")

    resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "fallback.recipient@example.com"}
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["delivery_mode"] == "simulated_fallback"
    assert "Connection refused" in data["message"]

    # Verify that the session is still active and can be verified
    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "fallback.recipient@example.com",
            "otp_code": data["otp_code"],
            "session_id": data["session_id"]
        }
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

def test_send_otp_email_empty_to_email():
    success, err = send_otp_email("", "123456")
    assert success is False
    assert "recipient email address is required" in err.lower()

    success, err = send_otp_email("   ", "123456")
    assert success is False
    assert "recipient email address is required" in err.lower()

def test_is_smtp_configured_whitespace_host(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "    ")
    assert is_smtp_configured() is False

@patch("app.core.mailer.smtplib.SMTP")
def test_send_otp_email_connect_error(mock_smtp_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.invalid-domain-passkhadam.org")
    monkeypatch.setenv("SMTP_PORT", "587")

    mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, b"Service not available")

    success, err = send_otp_email("worker@passkhadam.org", "729415")
    assert success is False
    assert "failed to connect" in err.lower()

@patch("app.core.mailer.smtplib.SMTP")
def test_send_otp_email_generic_exception(mock_smtp_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_PORT", "587")

    mock_smtp_cls.side_effect = RuntimeError("Socket timeout")

    success, err = send_otp_email("worker@passkhadam.org", "729415")
    assert success is False
    assert "smtp dispatch error" in err.lower()

@patch("app.core.mailer.smtplib.SMTP")
def test_send_otp_email_no_credentials_starttls(mock_smtp_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "mail.internal-relay.org")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")

    mock_server = MagicMock()
    mock_smtp_cls.return_value.__enter__.return_value = mock_server

    success, err = send_otp_email("worker@passkhadam.org", "729415")
    assert success is True
    assert err is None
    mock_server.login.assert_not_called()
    mock_server.send_message.assert_called_once()

@patch("app.core.mailer.smtplib.SMTP_SSL")
def test_send_otp_email_no_credentials_ssl(mock_smtp_ssl_cls, monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "mail.internal-relay.org")
    monkeypatch.setenv("SMTP_PORT", "465")
    monkeypatch.setenv("SMTP_USER", "")
    monkeypatch.setenv("SMTP_PASSWORD", "")

    mock_server = MagicMock()
    mock_smtp_ssl_cls.return_value.__enter__.return_value = mock_server

    success, err = send_otp_email("worker@passkhadam.org", "729415")
    assert success is True
    assert err is None
    mock_server.login.assert_not_called()
    mock_server.send_message.assert_called_once()

@patch("app.core.mailer.is_smtp_configured")
def test_send_email_otp_endpoint_simulation_fallback_when_unconfigured(mock_is_configured):
    mock_is_configured.return_value = False

    resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "unconfigured@example.com"}
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["success"] is True
    assert data["delivery_mode"] == "simulated"
    assert "Verification code successfully dispatched" in data["message"]

def test_build_otp_email_message_newline_injection_rejected():
    with pytest.raises(ValueError, match="newline"):
        build_otp_email_message("recipient@example.com\nBcc: evil@example.com", "123456")

    with pytest.raises(ValueError, match="newline"):
        build_otp_email_message("recipient@example.com", "123456", from_email="sender@example.com\r\nSubject: Injected")

    with pytest.raises(ValueError, match="newline"):
        build_otp_email_message("recipient@example.com", "123456", subject="Subject\r\nBcc: evil@example.com")

def test_send_otp_email_newline_injection_rejected():
    success, err = send_otp_email("victim@example.com\r\nBcc: attacker@example.com", "123456")
    assert success is False
    assert "newline" in err.lower()

    # Reject newline in otp_code
    success_otp, err_otp = send_otp_email("victim@example.com", "123\n456")
    assert success_otp is False
    assert "newline" in err_otp.lower()

    # Reject newline in subject
    success_subj, err_subj = send_otp_email("victim@example.com", "123456", subject="Subject\r\nBcc: evil@example.com")
    assert success_subj is False
    assert "newline" in err_subj.lower()

def test_build_otp_email_message_otp_newline_and_html_escaping():
    with pytest.raises(ValueError, match="newline"):
        build_otp_email_message("recipient@example.com", "123\r\n456")

    # Test HTML escaping of OTP
    msg = build_otp_email_message("recipient@example.com", "<script>alert('xss')</script>")
    payload = msg.get_payload()
    html_text = payload[1].get_payload(decode=True).decode("utf-8")
    assert "<script>" not in html_text
    assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html_text

