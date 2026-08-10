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


# The 68-point landmark predictor, not the 5-point default. It aligns the face
# chip far better when the head is turned or off-centre, which is what stops a
# student having to reproduce their registration pose to be recognised. Both
# sides of the comparison MUST use the same model — encodings built with one
# are not directly comparable to encodings built with the other, which is what
# `manage.py reencode_faces` exists to repair.
LANDMARK_MODEL = "large"

# Jitter only at registration: re-encoding the reference a few times over small
# random transforms and averaging gives a more stable vector, and enrolment
# happens once. Scans stay at 1 so the student isn't left waiting.
ENROLL_JITTERS = 5


def _ensure_lib() -> None:
    if face_recognition is None:
        raise FaceError(
            "face_recognition is not installed. Run `pip install -r requirements.txt`. "
            "On Windows, install `dlib-bin` first and then `face_recognition --no-deps` "
            "as shown in the README. "
            f"Original import error: {_import_error}"
        )


def _locate_faces(image) -> list:
    """Face boxes in the image, retrying once at higher upsampling.

    The second pass costs time but finds faces that are small in frame — a
    student standing back from the camera — so a valid photo isn't rejected as
    "no face detected".
    """
    locations = face_recognition.face_locations(image, number_of_times_to_upsample=1)
    if not locations:
        locations = face_recognition.face_locations(image, number_of_times_to_upsample=2)
    return locations


def _largest(locations: list) -> list:
    """The single biggest box, by area. Boxes are (top, right, bottom, left)."""
    return [max(locations, key=lambda box: (box[2] - box[0]) * (box[1] - box[3]))]


def encode_face(image_bytes: bytes) -> bytes:
    """Decode the image, locate one face, return the encoding pickled to bytes."""
    _ensure_lib()
    try:
        image = face_recognition.load_image_file(io.BytesIO(image_bytes))
    except Exception as exc:  # pragma: no cover - depends on Pillow
        raise FaceError(f"Could not read image: {exc}") from exc

    locations = _locate_faces(image)
    if not locations:
        raise FaceError("No face detected in the image. Re-take the photo with good lighting.")
    # Still rejected rather than resolved to the largest face: a reference photo
    # is worth getting unambiguously right, and the student is standing there.
    if len(locations) > 1:
        raise FaceError("Multiple faces detected. Capture a photo of one person only.")

    encodings = face_recognition.face_encodings(
        image,
        known_face_locations=locations,
        num_jitters=ENROLL_JITTERS,
        model=LANDMARK_MODEL,
    )
    if not encodings:
        raise FaceError("No face detected in the image. Re-take the photo with good lighting.")
    return pickle.dumps(encodings[0])


def load_encoding(blob: bytes) -> np.ndarray:
    return pickle.loads(blob)


def compare_to_encoding(image_bytes: bytes, stored_encoding_blob: bytes) -> Optional[float]:
    """Return Euclidean distance between the candidate face and stored encoding.

    Returns None if no face found in the candidate image.
    """
    _ensure_lib()
    image = face_recognition.load_image_file(io.BytesIO(image_bytes))
    locations = _locate_faces(image)
    if not locations:
        return None
    # The largest face wins, rather than whichever the detector happened to
    # return first: at scan time someone walking past in the background must not
    # become the candidate the student is judged on.
    encodings = face_recognition.face_encodings(
        image,
        known_face_locations=_largest(locations),
        num_jitters=1,
        model=LANDMARK_MODEL,
    )
    if not encodings:
        return None
    candidate = encodings[0]
    reference = load_encoding(stored_encoding_blob)
    distance = float(np.linalg.norm(candidate - reference))
    return distance
