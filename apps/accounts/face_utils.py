"""Wrappers around the `face_recognition` library.

Kept in `accounts` because student registration owns the reference encoding;
the attendance app imports `compare_to_encoding` for scan-time verification.
"""
from __future__ import annotations

import io
import pickle
from typing import Optional

import numpy as np

try:
    import face_recognition  # type: ignore
except ImportError as exc:  # pragma: no cover - surfaced at runtime
    face_recognition = None
    _import_error = exc
else:
    _import_error = None


class FaceError(Exception):
    """Raised when no face can be detected or encoded from an image."""


def _ensure_lib() -> None:
    if face_recognition is None:
        raise FaceError(
            "face_recognition is not installed. Run `pip install -r requirements.txt`. "
            "On Windows, install `dlib-bin` first and then `face_recognition --no-deps` "
            "as shown in the README. "
            f"Original import error: {_import_error}"
        )


def encode_face(image_bytes: bytes) -> bytes:
    """Decode the image, locate one face, return the encoding pickled to bytes."""
    _ensure_lib()
    try:
        image = face_recognition.load_image_file(io.BytesIO(image_bytes))
    except Exception as exc:  # pragma: no cover - depends on Pillow
        raise FaceError(f"Could not read image: {exc}") from exc

    encodings = face_recognition.face_encodings(image)
    if not encodings:
        raise FaceError("No face detected in the image. Re-take the photo with good lighting.")
    if len(encodings) > 1:
        raise FaceError("Multiple faces detected. Capture a photo of one person only.")
    return pickle.dumps(encodings[0])


def load_encoding(blob: bytes) -> np.ndarray:
    return pickle.loads(blob)


def compare_to_encoding(image_bytes: bytes, stored_encoding_blob: bytes) -> Optional[float]:
    """Return Euclidean distance between the candidate face and stored encoding.

    Returns None if no face found in the candidate image.
    """
    _ensure_lib()
    image = face_recognition.load_image_file(io.BytesIO(image_bytes))
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        return None
    candidate = encodings[0]
    reference = load_encoding(stored_encoding_blob)
    distance = float(np.linalg.norm(candidate - reference))
    return distance
