import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_send_email_otp_success():
    response = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "worker@passkhadam.org"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["success"] is True
    assert data["status"] == "SENT"
    assert data["session_id"].startswith("fb_em_sess_")
    assert "otp_code" in data
    assert data["email"] == "worker@passkhadam.org"
    assert data["simulated_email"]["to"] == "worker@passkhadam.org"

def test_verify_email_otp_with_generated_code():
    # 1. Send OTP
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "custom.worker@passkhadam.org"}
    )
    assert send_resp.status_code == 200
    otp_code = send_resp.json()["otp_code"]
    session_id = send_resp.json()["session_id"]

    # 2. Verify with correct code
    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "custom.worker@passkhadam.org",
            "otp_code": otp_code,
            "session_id": session_id
        }
    )
    assert verify_resp.status_code == 200
    data = verify_resp.json()
    assert data["verified"] is True
    assert "verified" in data["message"].lower()

def test_verify_email_otp_with_test_code_preset():
    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "test.user@passkhadam.org",
            "otp_code": "123456"
        }
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

def test_verify_email_otp_invalid_code_rejected():
    # Send code
    client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "reject.test@passkhadam.org"}
    )

    # Verify with wrong code
    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "reject.test@passkhadam.org",
            "otp_code": "999999"
        }
    )
    assert verify_resp.status_code == 400
    assert "Invalid verification code" in verify_resp.json()["detail"]

def test_send_email_otp_real_smtp_dispatch():
    from unittest.mock import patch
    with patch("app.api.endpoints.auth.is_smtp_configured", return_value=True), \
         patch("app.api.endpoints.auth.send_otp_email", return_value=(True, None)) as mock_send:
        response = client.post(
            "/api/v1/auth/send-email-otp",
            json={"email": "realuser@passkhadam.org"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["delivery_mode"] == "smtp"
        assert "Real verification email" in data["message"]
        mock_send.assert_called_once()
        assert mock_send.call_args[1]["to_email"] == "realuser@passkhadam.org"

def test_verify_email_otp_case_insensitive_and_whitespace():
    # Send to mixed case email
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "MixedCase.User@PassKhadam.Org"}
    )
    assert send_resp.status_code == 200
    otp_code = send_resp.json()["otp_code"]

    # Verify with lower-case and whitespace-padded code
    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "mixedcase.user@passkhadam.org",
            "otp_code": f"  {otp_code}  "
        }
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

def test_verify_email_otp_nonexistent_session_rejected():
    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "never_requested@example.com",
            "otp_code": "654321"
        }
    )
    assert verify_resp.status_code == 400
    assert "No active email OTP session found" in verify_resp.json()["detail"]

def test_verify_email_otp_expired_code():
    import time
    from app.api.endpoints.auth import ACTIVE_EMAIL_OTPS

    email = "expired.test@passkhadam.org"
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": email}
    )
    assert send_resp.status_code == 200
    otp_code = send_resp.json()["otp_code"]

    # Manually expire the session
    ACTIVE_EMAIL_OTPS[email]["expires_at"] = time.time() - 10

    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": email,
            "otp_code": otp_code
        }
    )
    assert verify_resp.status_code == 400
    assert "expired" in verify_resp.json()["detail"].lower()

def test_verify_email_otp_integer_code_coercion():
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "int_test@passkhadam.org"}
    )
    assert send_resp.status_code == 200
    otp_code = int(send_resp.json()["otp_code"])

    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "int_test@passkhadam.org",
            "otp_code": otp_code
        }
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

def test_verify_email_otp_hyphenated_and_spaced_input():
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "spaced_test@passkhadam.org"}
    )
    assert send_resp.status_code == 200
    code = send_resp.json()["otp_code"]
    formatted_code = f" {code[:3]}-{code[3:]} "

    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "spaced_test@passkhadam.org",
            "otp_code": formatted_code
        }
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

def test_verify_email_otp_mismatched_session_id_rejected():
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": "sess_test@passkhadam.org"}
    )
    assert send_resp.status_code == 200
    code = send_resp.json()["otp_code"]

    verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={
            "email": "sess_test@passkhadam.org",
            "otp_code": code,
            "session_id": "fb_em_sess_wrong_id"
        }
    )
    assert verify_resp.status_code == 400
    assert "mismatched" in verify_resp.json()["detail"].lower()

def test_verify_email_otp_attempt_limit_throttling():
    email = "throttle_test@passkhadam.org"
    send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": email}
    )
    assert send_resp.status_code == 200
    code = send_resp.json()["otp_code"]

    # Submit 4 wrong attempts - should fail with invalid code
    for i in range(4):
        resp = client.post(
            "/api/v1/auth/verify-email-otp",
            json={"email": email, "otp_code": f"00000{i}"}
        )
        assert resp.status_code == 400
        assert "Invalid verification code" in resp.json()["detail"]

    # 5th wrong attempt should trigger lockout and invalidate session
    lockout_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": email, "otp_code": "000009"}
    )
    assert lockout_resp.status_code == 400
    assert "Too many failed verification attempts" in lockout_resp.json()["detail"]

    # Subsequent verification with correct code should fail because session is locked out
    subsequent_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": email, "otp_code": code}
    )
    assert subsequent_resp.status_code == 400
    assert "Too many failed verification attempts" in subsequent_resp.json()["detail"]

    # Requesting a new OTP should reset the lockout and allow verification
    new_send_resp = client.post(
        "/api/v1/auth/send-email-otp",
        json={"email": email}
    )
    assert new_send_resp.status_code == 200
    new_code = new_send_resp.json()["otp_code"]

    new_verify_resp = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": email, "otp_code": new_code}
    )
    assert new_verify_resp.status_code == 200
    assert new_verify_resp.json()["verified"] is True

def test_verify_phone_otp_integer_coercion():
    send_resp = client.post(
        "/api/v1/auth/send-otp",
        json={"phone": "+91 9876543210"}
    )
    assert send_resp.status_code == 200

    verify_resp = client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": "+91 9876543210",
            "otp": 729415
        }
    )
    assert verify_resp.status_code == 200
    assert verify_resp.json()["verified"] is True

def test_verify_email_otp_none_and_empty_field_fallbacks():
    # 1. Body sends otp_code: None, but otp: "729415"
    resp1 = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": "fallback_test1@passkhadam.org", "otp_code": None, "otp": "729415"}
    )
    assert resp1.status_code == 200
    assert resp1.json()["verified"] is True

    # 2. Body sends otp_code: "", but otp: 729415 (integer)
    resp2 = client.post(
        "/api/v1/auth/verify-email-otp",
        json={"email": "fallback_test2@passkhadam.org", "otp_code": "", "otp": 729415}
    )
    assert resp2.status_code == 200
    assert resp2.json()["verified"] is True

def test_verify_phone_otp_none_and_empty_field_fallbacks():
    # 1. Body sends otp: None, but otp_code: "729415"
    resp1 = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": "+91 9876543210", "otp": None, "otp_code": "729415"}
    )
    assert resp1.status_code == 200
    assert resp1.json()["verified"] is True

    # 2. Body sends otp: "", but otp_code: 729415 (integer)
    resp2 = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": "+91 9876543210", "otp": "", "otp_code": 729415}
    )
    assert resp2.status_code == 200
    assert resp2.json()["verified"] is True

def test_verify_phone_otp_mismatched_session_id_rejected():
    send_resp = client.post(
        "/api/v1/auth/send-otp",
        json={"phone": "+91 9876543219"}
    )
    assert send_resp.status_code == 200

    verify_resp = client.post(
        "/api/v1/auth/verify-otp",
        json={
            "phone": "+91 9876543219",
            "otp": "729415",
            "session_id": "fb_sess_wrong_id"
        }
    )
    assert verify_resp.status_code == 400
    assert "mismatched" in verify_resp.json()["detail"].lower()

def test_verify_phone_otp_attempt_limit_throttling():
    phone = "+91 9876543299"
    send_resp = client.post(
        "/api/v1/auth/send-otp",
        json={"phone": phone}
    )
    assert send_resp.status_code == 200

    # 4 wrong attempts
    for i in range(4):
        resp = client.post(
            "/api/v1/auth/verify-otp",
            json={"phone": phone, "otp": f"00000{i}"}
        )
        assert resp.status_code == 400
        assert "Invalid OTP code" in resp.json()["detail"]

    # 5th wrong attempt triggers lockout
    lockout_resp = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": phone, "otp": "000009"}
    )
    assert lockout_resp.status_code == 400
    assert "Too many failed verification attempts" in lockout_resp.json()["detail"]

    # Subsequent verification is locked out
    subsequent_resp = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": phone, "otp": "729415"}
    )
    assert subsequent_resp.status_code == 400
    assert "Too many failed verification attempts" in subsequent_resp.json()["detail"]

    # Resending OTP clears lockout
    new_send = client.post(
        "/api/v1/auth/send-otp",
        json={"phone": phone}
    )
    assert new_send.status_code == 200

    new_verify = client.post(
        "/api/v1/auth/verify-otp",
        json={"phone": phone, "otp": "729415"}
    )
    assert new_verify.status_code == 200
    assert new_verify.json()["verified"] is True


