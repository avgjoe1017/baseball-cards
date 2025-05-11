import base64
import hashlib
import json
import os

import nacl.exceptions
import nacl.signing
import requests
from cachetools import TTLCache
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from dotenv import load_dotenv
from flask import Flask, Response, jsonify, request

load_dotenv()

app = Flask(__name__)

# Configuration
EBAY_CLIENT_SECRET = os.getenv("EBAY_CLIENT_SECRET")
EBAY_VERIFICATION_TOKEN = os.getenv("EBAY_VERIFICATION_TOKEN")
NOTIFICATION_ENDPOINT_URL = os.getenv("NOTIFICATION_ENDPOINT_URL")

# Public Key Cache
# PUBLIC_KEY_CACHE = {} # Replaced by TTLCache
PUBLIC_KEY_ENDPOINT = "https://api.ebay.com/commerce/notification/v1/public_key/"

# Cache for public keys with a TTL of 1 hour
public_key_cache = TTLCache(maxsize=10, ttl=3600)


# Helper Functions
def get_public_key(key_id: str):
    if key_id in public_key_cache:  # Use key_id as the cache key
        return public_key_cache[key_id]
    try:
        response = requests.get(f"{PUBLIC_KEY_ENDPOINT}{key_id}")
        response.raise_for_status()
        key_data = response.json()
        pem_key_string = key_data.get("key")
        if not pem_key_string:
            print(f"Error: 'key' field not found in response for key_id {key_id}")
            return None

        # Ensure the key is in PEM format for load_pem_public_key
        if "BEGIN PUBLIC KEY" not in pem_key_string:
            final_pem_string = (
                f"-----BEGIN PUBLIC KEY-----\n{pem_key_string}\n"
                f"-----END PUBLIC KEY-----"
            )
        else:
            final_pem_string = pem_key_string

        # Load the PEM public key using the cryptography library
        # This is the call that test_get_public_key expects.
        public_key_object = load_pem_public_key(final_pem_string.encode("utf-8"))

        # Cache the loaded cryptography public key object
        public_key_cache[key_id] = public_key_object
        return public_key_object

    except Exception as e:
        print(f"Error fetching public key {key_id}: {e}")
        return None


def verify_signature(request_body_bytes, timestamp, signature_base64, key_id):
    public_key_obj = get_public_key(key_id)
    verify_key = (
        public_key_obj
        if isinstance(public_key_obj, nacl.signing.VerifyKey)
        else nacl.signing.VerifyKey(public_key_obj)
    )
    if not public_key_obj:
        return False

    message_to_verify = request_body_bytes + timestamp.encode("utf-8")
    decoded_signature = base64.b64decode(signature_base64)

    try:
        # The verify method expects raw signature bytes.
        verify_key.verify(message_to_verify, decoded_signature)
        return True
    except (nacl.exceptions.BadSignatureError, ValueError):
        return False


def log_error(message):
    print(f"ERROR: {message}")


def log_debug(message):
    print(f"DEBUG: {message}")


@app.route("/", methods=["GET"])
def handle_ebay_validation():
    challenge_code = request.args.get("challenge_code")
    if not challenge_code:
        print("Validation attempt missing challenge code")
        return "Challenge code missing", 400

    # Use the configured verification token and endpoint URL
    verification_token = EBAY_VERIFICATION_TOKEN
    endpoint = NOTIFICATION_ENDPOINT_URL

    if not verification_token:
        print("ERROR: EBAY_VERIFICATION_TOKEN environment variable not set!")
        return "Server configuration error: Missing verification token", 500
    if not endpoint:
        print("ERROR: NOTIFICATION_ENDPOINT_URL environment variable not set!")
        return "Server configuration error: Missing endpoint URL", 500

    # Hash Calculation (SHA256, Hex Digest) - Order matters!
    hasher = hashlib.sha256()
    hasher.update(challenge_code.encode("utf-8"))
    hasher.update(verification_token.encode("utf-8"))
    hasher.update(endpoint.encode("utf-8"))
    response_hash = hasher.hexdigest()

    print(f"Received challenge code: {challenge_code}")
    print(f"Using Verification Token: {verification_token[:4]}...")  # Log partial token
    print(f"Using Endpoint URL: {endpoint}")
    print(f"Calculated response hash: {response_hash}")

    # Prepare and return JSON response
    response_data = {"challengeResponse": response_hash}
    response = jsonify(response_data)
    response.status_code = 200
    return response


@app.route("/ebay-notifications", methods=["POST"])
def ebay_notifications():
    signature_header = request.headers.get("X-EBAY-SIGNATURE")
    if not signature_header:
        return Response("Signature header missing", status=401)

    try:
        details = dict(item.split("=") for item in signature_header.split(","))
        key_id = details.get("kid")
        signature_base64 = details.get("sig")
        timestamp = details.get("ts")
    except ValueError:
        return Response("Invalid signature header format", status=401)

    request_body_bytes = request.get_data()
    if verify_signature(request_body_bytes, timestamp, signature_base64, key_id):
        log_debug("Signature verified successfully.")
        # Process the payload after successful signature verification
        try:
            payload = json.loads(request_body_bytes.decode("utf-8"))
            metadata = payload.get("metadata", {})
            notification_type = metadata.get("topic")

            if notification_type == "marketplace.account.deletion":
                data_payload = payload.get("data", {})
                user_id = data_payload.get("userId")
                if user_id:
                    print(f"Processing account deletion request for user ID: {user_id}")
                else:
                    print(
                        "Received 'marketplace.account.deletion' but 'userId' "
                        "is missing in data payload."
                    )
            else:
                print(f"Received valid notification. Type: {notification_type}")
            return Response(status=204)  # Return 204 after processing
        except json.JSONDecodeError:
            return Response("Invalid JSON payload", status=400)
        except Exception as e:
            return Response(f"Error processing notification: {e}", status=500)
    else:
        log_error("Signature verification failed.")
        return Response(status=401)


if __name__ == "__main__":
    # Use environment variables for host and port if available, otherwise default
    host = os.getenv("FLASK_RUN_HOST", "0.0.0.0")
    port = int(os.getenv("FLASK_RUN_PORT", 5000))
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in (
        "true",
        "1",
        "t",
    )
    app.run(host=host, port=port, debug=debug_mode)
