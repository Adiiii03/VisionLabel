import os
import uuid
import io
from datetime import datetime

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from flask import Flask, render_template, request, redirect, url_for, abort
from werkzeug.utils import secure_filename
from PIL import Image, ImageDraw, ImageFont, ImageOps
from dotenv import load_dotenv

# Load environment variables from .env (for local dev)
load_dotenv()

app = Flask(__name__)

# ---------- Config ----------
UPLOAD_FOLDER = os.path.join("static", "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB limit

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
DRY_RUN = os.getenv("REKOGNITION_DRY_RUN", "false").lower() == "true"

# Create Rekognition client only if not in dry-run
rekognition = None
if not DRY_RUN:
    rekognition = boto3.client("rekognition", region_name=AWS_REGION)

# ---------- Helpers ----------
def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS

def unique_name(original_name: str, prefix: str = "") -> str:
    base = secure_filename(original_name)
    stem, ext = os.path.splitext(base)
    return f"{prefix}{stem}_{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}_{uuid.uuid4().hex[:8]}{ext or '.jpg'}"

def pil_auto_prepare(pil_img: Image.Image) -> Image.Image:
    """Auto-orient based on EXIF and convert to RGB (handles PNG transparency & JPEG saving)."""
    pil_img = ImageOps.exif_transpose(pil_img)
    if pil_img.mode not in ("RGB", "RGBA"):
        pil_img = pil_img.convert("RGB")
    if pil_img.mode == "RGBA":
        # Flatten transparency against white for consistent saving/drawing
        bg = Image.new("RGB", pil_img.size, (255, 255, 255))
        bg.paste(pil_img, mask=pil_img.split()[3])
        pil_img = bg
    return pil_img

def draw_label_box(draw: ImageDraw.ImageDraw, xy_box, label_text, font=None):
    """Draw rectangle and label with a filled background for readability."""
    (left, top, right, bottom) = xy_box
    # Box
    draw.rectangle([left, top, right, bottom], outline=(255, 0, 0), width=3)

    # Text bg
    if not font:
        try:
            font = ImageFont.truetype("arial.ttf", 16)
        except:
            font = ImageFont.load_default()

    text_w, text_h = draw.textbbox((0, 0), label_text, font=font)[2:]
    pad = 4
    bg_left = left
    bg_top = max(top - text_h - 2 * pad, 0)
    bg_right = left + text_w + 2 * pad
    bg_bottom = bg_top + text_h + 2 * pad

    # Semi-opaque background (simulate alpha by blending a filled rectangle)
    draw.rectangle([bg_left, bg_top, bg_right, bg_bottom], fill=(255, 255, 255))
    draw.text((bg_left + pad, bg_top + pad), label_text, fill=(255, 0, 0), font=font)

# ---------- Routes ----------
@app.route("/")
def index():
    return render_template("index.html")

@app.errorhandler(413)
def too_large(_):
    return "File too large (max 10 MB).", 413

@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return "No file uploaded", 400

    file = request.files["file"]
    if file.filename == "":
        return "No selected file", 400

    if not allowed_file(file.filename):
        return "Invalid file type. Only JPG and PNG allowed.", 400

    # Generate unique names
    original_name = unique_name(file.filename, prefix="")
    labeled_name = unique_name(file.filename, prefix="labeled_")

    # Save original image safely
    save_path = os.path.join(app.config["UPLOAD_FOLDER"], original_name)

    # Open with PIL first to normalize orientation/mode
    try:
        pil = Image.open(file.stream)
        pil = pil_auto_prepare(pil)
        pil.save(save_path, quality=95)
    except Exception as e:
        return f"Image processing error: {e}", 400

    # Read bytes for Rekognition
    with open(save_path, "rb") as f:
        image_bytes = f.read()

    labels = []
    try:
        if DRY_RUN:
            # Fake a single box centered with a dummy label to test UI
            pil_w, pil_h = pil.size
            labels = [
                {
                    "Name": "SampleObject",
                    "Confidence": 99.1,
                    "Instances": [
                        {
                            "BoundingBox": {
                                "Left": 0.25,
                                "Top": 0.25,
                                "Width": 0.5,
                                "Height": 0.5,
                            },
                            "Confidence": 99.1,
                        }
                    ],
                }
            ]
        else:
            resp = rekognition.detect_labels(
                Image={"Bytes": image_bytes}, MaxLabels=10, MinConfidence=70
            )
            labels = resp.get("Labels", [])
    except (BotoCoreError, ClientError) as e:
        # Clean error message
        return (
            f"AWS Rekognition error: {getattr(e, 'response', {}).get('Error', {}).get('Message', str(e))}",
            500,
        )

    # Draw boxes
    draw = ImageDraw.Draw(pil)
    img_w, img_h = pil.size
    for label in labels:
        for inst in label.get("Instances", []):
            box = inst.get("BoundingBox")
            if not box:
                continue
            left = img_w * box.get("Left", 0)
            top = img_h * box.get("Top", 0)
            width = img_w * box.get("Width", 0)
            height = img_h * box.get("Height", 0)
            xy = (left, top, left + width, top + height)
            text = f"{label['Name']} ({round(label.get('Confidence', 0.0), 1)}%)"
            draw_label_box(draw, xy, text)

    # Save labeled image
    labeled_path = os.path.join(app.config["UPLOAD_FOLDER"], labeled_name)
    pil.save(labeled_path, quality=95)

    return render_template(
        "result.html",
        original_image=original_name,
        labeled_image=labeled_name,
        labels=labels,
    )

if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
