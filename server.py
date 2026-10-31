"""
Backend for "What's in the picture?"

Setup:
    pip install flask inference-sdk pillow boto3
    ROBOFLOW_API_KEY and ADMIN_PASSWORD come from /etc/roboflow.env
Put sample photos in an "images" folder next to this file.
"""
import hmac
import json
import os
import shutil
from io import BytesIO

import boto3
from flask import Flask, jsonify, request, send_from_directory
from inference_sdk import InferenceHTTPClient
from PIL import Image

#MODEL_ID = "printed-circuit-board/3"
#MODEL_ID = "poker-cards-cxcvz/1"
MODEL_ID = "rfdetr-base"

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
IMAGE_DIR = os.path.join(BASE_DIR, "images")
TRASH_DIR = os.path.join(BASE_DIR, "trash")    # deleted samples go here, not gone for good
# Saved Roboflow answers for samples, one folder per model so switching models starts fresh.
CACHE_DIR = os.path.join(BASE_DIR, "results", MODEL_ID.replace("/", "_"))
MAX_SIDE = 1280                                 # samples are shrunk to this before checking
ALLOWED = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")

# Email alerts through Amazon SES (the EC2 instance's IAM role needs ses:SendEmail).
# Both addresses can be overridden in /etc/roboflow.env.
ALERT_TO = os.environ.get("ALERT_TO", "carroll.david.aws@gmail.com")
ALERT_FROM = os.environ.get("ALERT_FROM", "carroll.david.aws@gmail.com")
SES_REGION = os.environ.get("SES_REGION", "us-east-1")
# Visitors with these IPs never trigger an alert (comma-separated, set IGNORE_IPS in /etc/roboflow.env).
IGNORE_IPS = {ip.strip() for ip in os.environ.get("IGNORE_IPS", "").split(",") if ip.strip()}
SES = boto3.client("ses", region_name=SES_REGION)

CLIENT = InferenceHTTPClient(
    api_url="https://serverless.roboflow.com",
    api_key=os.environ["ROBOFLOW_API_KEY"],
)

app = Flask(__name__)


def sample_path(name):
    """Full path of a sample image, or None if the name isn't a real sample."""
    safe = os.path.basename(str(name))              # blocks ../ tricks
    if safe != name or os.path.splitext(safe)[1].lower() not in ALLOWED:
        return None
    path = os.path.join(IMAGE_DIR, safe)
    return path if os.path.isfile(path) else None


def cache_file(name):
    return os.path.join(CACHE_DIR, name + ".json")


def visitor_ip():
    """Visitor's IP. Apache passes the real one in X-Forwarded-For; fall back to the direct address."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def send_alert(subject, body):
    """Email an alert. Never lets an email problem break the page."""
    if visitor_ip() in IGNORE_IPS:
        return                                    # that's you, no email needed
    try:
        SES.send_email(
            Source=ALERT_FROM,
            Destination={"ToAddresses": [ALERT_TO]},
            Message={
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": f"{body}\n\nVisitor IP: {visitor_ip()}\n(direct address: {request.remote_addr})"}},
            },
        )
    except Exception as err:
        app.logger.warning("Alert email failed: %s", err)


@app.get("/")
def index():
    return send_from_directory(BASE_DIR, "index.html")


@app.get("/api/samples")
def samples():
    if not os.path.isdir(IMAGE_DIR):
        return jsonify([])
    names = sorted(
        f for f in os.listdir(IMAGE_DIR)
        if os.path.splitext(f)[1].lower() in ALLOWED
    )
    return jsonify(names)


@app.get("/api/samples/detect/<name>")
def detect_sample(name):
    # Checks a sample with Roboflow once, saves the answer, and reuses it after that.
    path = sample_path(name)
    if path is None:
        return jsonify(error="No such sample"), 404

    saved = cache_file(name)
    if os.path.isfile(saved):
        with open(saved) as f:
            cached = json.load(f)
        cached["cached"] = True          # lets the page know this answer was already saved
        send_alert(f"Sample viewed (saved result): {name}",
                   f"Someone clicked {name}. Saved answer reused, no Roboflow credit used.")
        return jsonify(cached)

    image = Image.open(path).convert("RGB")
    image.thumbnail((MAX_SIDE, MAX_SIDE))
    result = CLIENT.infer(image, model_id=MODEL_ID)
    # Record the size Roboflow saw, so the page can line the boxes up.
    result["image"] = {"width": image.width, "height": image.height}

    os.makedirs(CACHE_DIR, exist_ok=True)
    with open(saved, "w") as f:
        json.dump(result, f)
    send_alert(f"Sample viewed (new Roboflow call): {name}",
               f"Someone clicked {name} for the first time. Roboflow was called and the answer saved.")
    return jsonify(result)


@app.post("/api/samples/delete")
def delete_samples():
    # Admin only: needs the password from the ADMIN_PASSWORD environment variable.
    if not ADMIN_PASSWORD:
        return jsonify(error="Deleting is switched off (no ADMIN_PASSWORD set)."), 403
    body = request.get_json(silent=True) or {}
    if not hmac.compare_digest(str(body.get("password", "")), ADMIN_PASSWORD):
        return jsonify(error="Wrong password."), 403

    os.makedirs(TRASH_DIR, exist_ok=True)
    moved, skipped = [], []
    for name in body.get("files", []):
        path = sample_path(name)
        if path is None:
            skipped.append(name)
            continue
        shutil.move(path, os.path.join(TRASH_DIR, name))
        if os.path.isfile(cache_file(name)):          # drop its saved answer too
            os.remove(cache_file(name))
        moved.append(name)
    return jsonify(moved=moved, skipped=skipped)


@app.get("/images/<path:name>")
def sample_image(name):
    return send_from_directory(IMAGE_DIR, name)


@app.post("/api/detect")
def detect():
    # Visitors' own uploads: always checked live, never saved.
    upload = request.files.get("image")
    if upload is None:
        return jsonify(error="No image uploaded"), 400
    try:
        image = Image.open(BytesIO(upload.read())).convert("RGB")
    except Exception:
        return jsonify(error="Could not read that image"), 400
    result = CLIENT.infer(image, model_id=MODEL_ID)
    send_alert("Visitor uploaded their own photo",
               "Someone uploaded their own image. It was checked live with Roboflow and not saved.")
    return jsonify(result)


if __name__ == "__main__":
    app.run(debug=True)
