from __future__ import annotations
import os
from pathlib import Path


MODEL_PATH = os.getenv("LOGO_MODEL_PATH", "./models/logo_yolov8.pt")


def detect_logos(image_path: str, conf_threshold: float = 0.35) -> list[dict]:
    """
    Detect brand logos in an image using YOLOv8 fine-tuned on LogoDet-3K.

    Returns a list of detections:
    [{"brand": "...", "confidence": 0.0, "bbox": [x1, y1, x2, y2]}]

    If the model file is not present, returns an empty list with a warning.
    The model must be fine-tuned separately — see notebooks/logo_training.ipynb.
    """
    if not Path(MODEL_PATH).exists():
        import warnings
        warnings.warn(
            f"Logo detection model not found at {MODEL_PATH}. "
            "Skipping logo detection. Download or train the model and set "
            "LOGO_MODEL_PATH env var.",
            RuntimeWarning,
            stacklevel=2,
        )
        return []

    try:
        from ultralytics import YOLO
        model   = YOLO(MODEL_PATH)
        results = model(image_path, conf=conf_threshold, verbose=False)

        detections = []
        for box in results[0].boxes:
            detections.append({
                "brand":      model.names[int(box.cls)],
                "confidence": round(float(box.conf), 3),
                "bbox":       [round(v, 1) for v in box.xyxy[0].tolist()],
            })
        return detections
    except Exception as e:
        return []


def logos_to_org_names(detections: list[dict]) -> list[str]:
    """Extract unique organisation names from logo detections above threshold."""
    return list({d["brand"] for d in detections if d["confidence"] >= 0.40})
