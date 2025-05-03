import base64
import hashlib
import json
import os
import time

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
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
PUBLIC_KEY_CACHE = {}
PUBLIC_KEY_ENDPOINT = (
    "https://api.ebay.com/commerce/notification/v1/public_key/"
)


# Helper Functions
def get_public_key(key_id: str):
    if key_id in PUBLIC_KEY_CACHE:
        return PUBLIC_KEY_CACHE[key_id]
    try:
        response = requests.get(f"{PUBLIC_KEY_ENDPOINT}{key_id}")
        response.raise_for_status()
        key_data = response.json()
        pem_key = key_data.get("key")
        if not pem_key:
            return None
        public_key = load_pem_public_key(pem_key.encode("utf-8"))
        PUBLIC_KEY_CACHE[key_id] = public_key
        return public_key
    except Exception:
        return None


def verify_signature(request_body_bytes: bytes, signature_header: str):
    try:
        header_parts = {
            item.split("=")[0]: item.split("=")[1].strip('"')
            for item in signature_header.split(",")
        }
        signature = base64.b64decode(header_parts.get("signature"))
        key_id = header_parts.get("kid")
        timestamp = int(header_parts.get("t"))
        algo = header_parts.get("alg")
        if not signature or not key_id or not timestamp or not algo:
            return False
        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            return False
        public_key = get_public_key(key_id)
        if not public_key:
            return False
        message_to_verify = request_body_bytes + str(timestamp).encode("utf-8")
        if algo.upper() == "SHA256WITHRSA":
            padding_algo = padding.PKCS1v15()
            hash_algo = hashes.SHA256()
        else:
            return False
        public_key.verify(
            signature, message_to_verify, padding_algo, hash_algo
        )
        return True
    except InvalidSignature:
        return False
    except Exception:
        return False


@app.route("/", methods=["GET"])
def handle_ebay_validation():
    challenge_code = request.args.get("challenge_code")
    if not challenge_code:
        print("Validation attempt missing challenge code")
        return "Challenge code missing", 400

    verification_token = os.environ.get("EBAY_VERIFICATION_TOKEN")
    if not verification_token:
        print("ERROR: EBAY_VERIFICATION_TOKEN environment variable not set!")
        return "Server configuration error", 500

    endpoint = "https://baseball-cards.onrender.com"  # Must match eBay config

    # Hash Calculation (SHA256, Hex Digest)
    hasher = hashlib.sha256()
    hasher.update(challenge_code.encode("utf-8"))
    hasher.update(verification_token.encode("utf-8"))
    hasher.update(endpoint.encode("utf-8"))
    response_hash = hasher.hexdigest()

    print(f"Received challenge code: {challenge_code}")  # Temporary logging
    print(f"Calculated response hash: {response_hash}")  # Temporary logging

    # Prepare and return JSON response
    response_data = {"challengeResponse": response_hash}
    response = jsonify(response_data)
    response.status_code = 200
    return response


@app.route("/ebay-notifications", methods=["GET", "POST"])
def ebay_notifications():
    if request.method == "GET":
        challenge_code = request.args.get("challenge_code")
        if not challenge_code:
            return Response("Challenge code missing", status=400)
        if not EBAY_VERIFICATION_TOKEN or not NOTIFICATION_ENDPOINT_URL:
            return Response("Server configuration error", status=500)
        hasher = hashlib.sha256()
        hasher.update(challenge_code.encode("utf-8"))
        hasher.update(EBAY_VERIFICATION_TOKEN.encode("utf-8"))
        hasher.update(NOTIFICATION_ENDPOINT_URL.encode("utf-8"))
        challenge_response = base64.b64encode(hasher.digest()).decode("utf-8")
        return Response(
            json.dumps({"challengeResponse": challenge_response}),
            content_type="application/json",
            status=200,
        )
    elif request.method == "POST":
        signature = request.headers.get("X-EBAY-SIGNATURE")
        if not signature:
            return Response("Signature header missing", status=401)
        request_body_bytes = request.get_data()
        is_signature_valid = verify_signature(request_body_bytes, signature)
        if not is_signature_valid:
            return Response("Invalid signature", status=401)
        try:
            payload = json.loads(request_body_bytes.decode("utf-8"))
            metadata = payload.get("metadata", {})
            notification_type = metadata.get("topic")
            if notification_type == "marketplace.account.deletion":
                user_id_field = payload.get("data", {}).get("userId")
                if user_id_field:
                    print(f"Processing deletion for user ID: {user_id_field}")
            return Response(status=204)
        except Exception:
            return Response("Error processing notification", status=500)
    else:
        return Response("Method Not Allowed", status=405)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
