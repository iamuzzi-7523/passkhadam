import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_demo_login_all_roles():
    """Verify real login and demo-login for all 5 roles."""
    roles = ["WORKER", "EMPLOYER", "GOVERNMENT", "ADMIN", "AADHAAR"]
    for role in roles:
        response = client.post(f"/api/v1/auth/demo-login/{role}")
        assert response.status_code == 200, f"Demo login failed for {role}"
        data = response.json()
        assert "access_token" in data
        assert data["user"]["role"] == role
        assert data["user"]["email"] is not None

def test_firebase_phone_otp_flow():
    """Verify Firebase SMS / Phone OTP gateway simulation."""
    phone = "+91 9876543210"
    # 1. Send OTP
    send_resp = client.post("/api/v1/auth/send-otp", json={"phone": phone})
    assert send_resp.status_code == 200
    send_data = send_resp.json()
    assert send_data["success"] is True
    assert "session_id" in send_data
    assert "Firebase" in send_data["simulated_sms"]
    assert send_data["expires_in"] == 300

    # 2. Verify invalid OTP rejection
    bad_resp = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "000000"})
    assert bad_resp.status_code == 400

    # 3. Verify valid OTP acceptance
    # For demo phone "+91 9876543210", OTP is "729415"
    good_resp = client.post("/api/v1/auth/verify-otp", json={"phone": phone, "otp": "729415"})
    assert good_resp.status_code == 200
    assert good_resp.json()["verified"] is True

def test_network_and_ipfs_configuration_endpoints():
    """Verify blockchain networks and IPFS multi-provider configuration endpoints."""
    # 1. Get network config
    resp = client.get("/api/v1/admin/network-config")
    assert resp.status_code == 200
    data = resp.json()
    assert "supported_networks" in data
    assert "supported_ipfs_providers" in data
    assert len(data["supported_networks"]) >= 3 # Hardhat, Polygon Amoy, Ethereum Sepolia
    assert len(data["supported_ipfs_providers"]) >= 3 # Local, Pinata, Kubo

    # 2. Test diagnostic connectivity
    diag_resp = client.post("/api/v1/admin/test-connectivity")
    assert diag_resp.status_code == 200
    diag_data = diag_resp.json()
    assert diag_data["blockchain"]["status"] == "CONNECTED"
    assert diag_data["ipfs"]["status"] == "OPERATIONAL"
    assert diag_data["overall_health"] == "OPTIMAL"
