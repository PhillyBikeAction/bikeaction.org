import base64
import logging
import mimetypes
import os
import urllib.parse
from io import BytesIO

import cv2
import interactions
import numpy as np
import requests
from django.conf import settings
from django.utils import timezone
from PIL import Image, ImageDraw


def detect_faces(image_bytes, max_dimension=1920):
    """
    Detect faces in an image using OpenCV Haar cascades.

    Args:
        image_bytes: Raw image bytes
        max_dimension: Maximum width or height for processing (to limit memory usage)

    Returns:
        List of dicts with xmin, ymin, xmax, ymax keys (in original image coordinates)
    """
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        return []

    original_height, original_width = img.shape[:2]
    scale = 1.0

    # Downsample if image is too large to prevent memory issues
    if max(original_width, original_height) > max_dimension:
        scale = max_dimension / max(original_width, original_height)
        new_width = int(original_width * scale)
        new_height = int(original_height * scale)
        img = cv2.resize(img, (new_width, new_height), interpolation=cv2.INTER_AREA)

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5)

    # Scale coordinates back to original image size
    return [
        {
            "xmin": int(x / scale),
            "ymin": int(y / scale),
            "xmax": int((x + w) / scale),
            "ymax": int((y + h) / scale),
        }
        for (x, y, w, h) in faces
    ]


def redact_image(image_file, plate_recognizer_response):
    """
    Redact license plates and faces from an image.

    Returns:
        BytesIO with redacted image, or None if nothing to redact
    """
    image_file.seek(0)
    image_bytes = image_file.read()

    boxes = []

    if plate_recognizer_response:
        for result in plate_recognizer_response.get("results", []):
            if result.get("plate") and result["plate"].get("box"):
                boxes.append(result["plate"]["box"])

    face_boxes = detect_faces(image_bytes)
    boxes.extend(face_boxes)

    if not boxes:
        return None

    image = Image.open(BytesIO(image_bytes))
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")

    draw = ImageDraw.Draw(image)
    for box in boxes:
        draw.rectangle(
            [box["xmin"], box["ymin"], box["xmax"], box["ymax"]],
            fill="black",
        )

    output = BytesIO()
    image.save(output, format=image.format or "JPEG")
    output.seek(0)
    return output


def submit_violation_report_to_ppa(violation_report):
    """Submit a violation report to PPA via Power Automate API."""

    if not settings.DEBUG:
        domain = settings.PPA_API_DOMAIN
        workflow = settings.PPA_API_WORKFLOW
        sig = settings.PPA_API_SIG

        if not all([domain, workflow, sig]):
            raise ValueError(
                "PPA API settings (PPA_API_DOMAIN, PPA_API_WORKFLOW, PPA_API_SIG) "
                "must be configured"
            )

        url = (
            f"https://{domain}:443/powerautomate/automations/direct/workflows/{workflow}"
            f"/triggers/manual/paths/invoke?api-version=1"
            f"&sp={urllib.parse.quote('/triggers/manual/run')}&sv=1.0&sig={sig}"
        )

    image = violation_report.submission.image
    image_name = os.path.basename(image.name)
    content_type = mimetypes.guess_type(image_name)[0] or "image/jpeg"

    plate_recognizer_response = violation_report.submission.plate_recognizer_response
    redacted_image = redact_image(image, plate_recognizer_response)

    if redacted_image:
        from django.core.files.base import ContentFile

        redacted_image.seek(0)
        violation_report.redacted_image.save(
            f"redacted_{image_name}",
            ContentFile(redacted_image.read()),
            save=True,
        )

        redacted_image.seek(0)
        image_content = base64.b64encode(redacted_image.read()).decode("utf-8")
    else:
        image.seek(0)
        image_content = base64.b64encode(image.read()).decode("utf-8")

    payload = {
        "dateObserved": violation_report.date_observed,
        "timeObserved": violation_report.time_observed,
        "make": violation_report.make,
        "model": violation_report.model,
        "bodyStyle": violation_report.body_style,
        "vehicleColor": violation_report.vehicle_color,
        "violationObserved": violation_report.violation_observed,
        "frequency": violation_report.occurrence_frequency,
        "blockNumber": violation_report.block_number,
        "streetName": violation_report.street_name,
        "zipCode": violation_report.zip_code,
        "citizenNotes": "",
        "attachments": [
            {
                "fileName": image_name,
                "fileContent": image_content,
                "contentType": content_type,
            }
        ],
    }

    headers = {
        "Content-Type": "application/json",
    }

    logging.info(
        f"Submitting violation report to PPA API (attachment size: {len(image_content)} bytes)"
    )

    if settings.DEBUG:
        import json

        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage

        logging.info("DEBUG mode: skipping actual API submission")
        submission_id = violation_report.submission.submission_id

        debug_payload = payload.copy()
        debug_payload["attachments"] = [
            {**a, "fileContent": "[BASE64_IMAGE_DATA]"} for a in payload["attachments"]
        ]
        payload_path = f"lazer/debug_redacted/{submission_id}_payload.json"
        if default_storage.exists(payload_path):
            default_storage.delete(payload_path)
        default_storage.save(
            payload_path, ContentFile(json.dumps(debug_payload, indent=2).encode())
        )
        payload_url = f"{settings.SITE_URL}/media/{payload_path}"

        image_path = f"lazer/debug_redacted/{submission_id}.jpg"
        if default_storage.exists(image_path):
            default_storage.delete(image_path)

        if redacted_image:
            redacted_image.seek(0)
            default_storage.save(image_path, ContentFile(redacted_image.read()))
            image_url = f"{settings.SITE_URL}/media/{image_path}"
            redacted = True
        else:
            image.seek(0)
            default_storage.save(image_path, ContentFile(image.read()))
            image_url = f"{settings.SITE_URL}/media/{image_path}"
            redacted = False

        print("\n*** DEBUG PPA SUBMISSION ***")
        print(f"    Payload: {payload_url}")
        print(f"    Image:   {image_url}")
        print(f"    Redacted: {redacted}")
        if not redacted:
            print("    (No plate_recognizer_response data - is this a new submission?)\n")
        else:
            print()

        return

    response = requests.post(url, json=payload, headers=headers, timeout=60)
    response.raise_for_status()

    response_data = response.json()
    service_id = response_data.get("itemId")

    violation_report.submitted = timezone.now()
    violation_report.service_id = service_id
    violation_report.submission_response = response_data
    violation_report.save()


def build_embed(violation_report):
    embed = interactions.Embed(
        title="Violation report from a new user submitted!",
        description=(
            "**New reporters need to be vetted.**\n\n"
            "Review this report and click the Approve or Reject button below."
        ),
        timestamp=timezone.now(),
    )
    embed.add_field("Date Observed", violation_report.date_observed, inline=True)
    embed.add_field("Time Observed", violation_report.time_observed, inline=True)
    embed.add_field("\u200b", "\u200b", inline=True)
    embed.add_field("Make", violation_report.make, inline=True)
    embed.add_field("Model", violation_report.model, inline=True)
    embed.add_field("Body Style", violation_report.body_style, inline=True)
    embed.add_field("Vehicle Color", violation_report.vehicle_color, inline=True)
    embed.add_field("\u200b", "\u200b", inline=True)
    embed.add_field("\u200b", "\u200b", inline=True)
    embed.add_field("Block Number", violation_report.block_number, inline=True)
    embed.add_field("Street Name", violation_report.street_name, inline=True)
    embed.add_field("Zip Code", violation_report.zip_code, inline=True)
    embed.add_field("Violation", violation_report.violation_observed)
    embed.add_field("Occurrence", violation_report.occurrence_frequency)
    embed.add_field("Additional", violation_report.additional_information)

    image_url = violation_report.submission.image.url
    if not image_url.startswith("http"):
        image_url = f"{settings.SITE_URL}{image_url}"
    embed.set_thumbnail(url=image_url)
    embed.add_field("View Image", f"[here]({image_url})")

    return embed
