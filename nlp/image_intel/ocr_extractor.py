from __future__ import annotations


def extract_text(image_path: str) -> str:
    """
    Run Tesseract OCR on an image after OpenCV preprocessing.
    Returns plain extracted text string.
    """
    try:
        import pytesseract
        import cv2

        img      = cv2.imread(image_path)
        gray     = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        denoised = cv2.fastNlMeansDenoising(gray, h=10)
        _, thresh = cv2.threshold(
            denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU
        )
        return pytesseract.image_to_string(thresh).strip()
    except Exception:
        return ""
