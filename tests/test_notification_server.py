import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import base64
import hashlib
from unittest.mock import MagicMock, patch

import nacl.encoding
import nacl.signing

from notification_server import app, get_public_key, public_key_cache, verify_signature


# --------------------------------------------------------------------------- #
# get_public_key                                                              #
# --------------------------------------------------------------------------- #
def test_get_public_key():
    public_key_cache.clear()  # Clear cache for test isolation
    pem_key = "-----BEGIN PUBLIC KEY-----\nmocked_key\n-----END PUBLIC KEY-----"

    with (
        patch("notification_server.requests.get") as mock_get,
        patch("notification_server.load_pem_public_key") as mock_load_key,
    ):
        # Configure mocked HTTP call
        mock_response = MagicMock()
        mock_response.status_code = 200  # Explicitly set a success status code
        mock_response.json.return_value = {"key": pem_key}  # formatted PEM already
        mock_get.return_value = mock_response

        # Mock the actual PEM loader
        mock_loaded_key = MagicMock(name="MockPublicKey")
        mock_load_key.return_value = mock_loaded_key

        key = get_public_key("mock_key_id")

        mock_get.assert_called_once()
        mock_load_key.assert_called_once_with(pem_key.encode("utf-8"))
        assert key == mock_loaded_key


# --------------------------------------------------------------------------- #
# verify_signature                                                            #
# --------------------------------------------------------------------------- #
def test_verify_signature():
    # 1. Generate a real Ed25519 key pair and a valid signature
    signing_key = nacl.signing.SigningKey.generate()
    verify_key = signing_key.verify_key
    body = b"mock_body"
    timestamp = "1678886400"

    sig_bytes = signing_key.sign(body).signature
    sig_b64 = base64.b64encode(sig_bytes).decode("utf-8")

    # 2. Create a single VerifyKey instance and mock its verify()
    verify_key_mock = verify_key
    verify_key_mock.verify = MagicMock(return_value=None)

    # 3. Patch get_public_key to return that mocked key
    with patch("notification_server.get_public_key", return_value=verify_key_mock):
        result = verify_signature(body, timestamp, sig_b64, "mock_key_id")

    assert result is True
    verify_key_mock.verify.assert_called_once()


# --------------------------------------------------------------------------- #
# eBay challenge validation                                                   #
# --------------------------------------------------------------------------- #
def test_handle_ebay_validation():
    client = app.test_client()
    challenge_code = "test_challenge_code"
    verification_token = "verification_token"
    endpoint_url = "webhook_endpoint_url"

    payload_for_hash = (
        challenge_code.encode() + verification_token.encode() + endpoint_url.encode()
    )
    expected_hash = hashlib.sha256(payload_for_hash).hexdigest()

    with (
        patch("notification_server.verify_signature", return_value=True),
        patch("notification_server.EBAY_VERIFICATION_TOKEN", verification_token),
        patch("notification_server.NOTIFICATION_ENDPOINT_URL", endpoint_url),
    ):
        resp = client.get(
            f"/?challenge_code={challenge_code}",
            headers={"X-EBAY-SIGNATURE": "mock_sig_header"},
        )

    assert resp.status_code == 200
    assert resp.get_json() == {"challengeResponse": expected_hash}


# --------------------------------------------------------------------------- #
# eBay notification POST                                                      #
# --------------------------------------------------------------------------- #
def test_ebay_notifications():
    client = app.test_client()
    mock_payload = {
        "metadata": {"topic": "marketplace.account.deletion"},
        "data": {"userId": "test_user_123"},
    }

    with (
        patch("notification_server.verify_signature", return_value=True),
        patch("notification_server.print") as mock_print,
    ):
        # Correctly formatted signature header
        mock_signature_header = "kid=mock_key_id,sig=mock_signature,ts=mock_timestamp"
        resp = client.post(
            "/ebay-notifications",
            json=mock_payload,
            headers={"X-EBAY-SIGNATURE": mock_signature_header},
        )

    assert resp.status_code == 204  # 204 No Content
    mock_print.assert_any_call(
        "Processing account deletion request for user ID: test_user_123"
    )
