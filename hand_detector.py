from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import shutil
import tempfile
from typing import Any

import cv2
import mediapipe as mp
import mediapipe as mp_package


# ✅ Forma correcta y estable de usar MediaPipe
mp_solutions = mp.solutions

from mediapipe.python import solution_base as mp_solution_base

from utils import StableCounter


def _redirect_mediapipe_resources_if_needed() -> None:
    """Avoid MediaPipe resource loading failures from non-ASCII project paths."""

    site_root = Path(mp_package.__file__).resolve().parent.parent
    if all(ord(char) < 128 for char in str(site_root)):
        return

    source_modules = site_root / "mediapipe" / "modules"
    target_root = Path(tempfile.gettempdir()) / "deteccion_dedos_mediapipe"
    target_modules = target_root / "mediapipe" / "modules"

    if not target_modules.exists():
        shutil.copytree(source_modules, target_modules, dirs_exist_ok=True)

    fake_solution_base = target_root / "mediapipe" / "python" / "solution_base.py"
    fake_solution_base.parent.mkdir(parents=True, exist_ok=True)
    mp_solution_base.__file__ = str(fake_solution_base)


@dataclass(frozen=True)
class FingerState:
    thumb: bool
    index: bool
    middle: bool
    ring: bool
    pinky: bool

    @property
    def count(self) -> int:
        return sum((self.thumb, self.index, self.middle, self.ring, self.pinky))

    def as_dict(self) -> dict[str, bool]:
        return {
            "thumb": self.thumb,
            "index": self.index,
            "middle": self.middle,
            "ring": self.ring,
            "pinky": self.pinky,
        }


@dataclass(frozen=True)
class HandDetection:
    handedness: str
    confidence: float
    raw_count: int
    stable_count: int
    fingers: FingerState
    landmarks: Any


class HandDetector:
    """MediaPipe-based single/multi-hand detector with finger-count logic."""

    FINGER_TIPS = {
        "thumb": 4,
        "index": 8,
        "middle": 12,
        "ring": 16,
        "pinky": 20,
    }
    FINGER_PIPS = {
        "index": 6,
        "middle": 10,
        "ring": 14,
        "pinky": 18,
    }
    FINGER_MCPS = {
        "index": 5,
        "middle": 9,
        "ring": 13,
        "pinky": 17,
    }

    def __init__(
        self,
        max_num_hands: int = 1,
        detection_confidence: float = 0.7,
        tracking_confidence: float = 0.7,
        stable_window: int = 7,
        preferred_handedness: str | None = None,
        thumb_mode: str = "auto",
    ) -> None:
        self.max_num_hands = max_num_hands
        self.preferred_handedness = preferred_handedness
        self.thumb_mode = thumb_mode

        _redirect_mediapipe_resources_if_needed()
        self.mp_hands = mp_solutions.hands
        self.mp_draw = mp_solutions.drawing_utils
        self.mp_styles = mp_solutions.drawing_styles
        self._hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=max_num_hands,
            model_complexity=0,
            min_detection_confidence=detection_confidence,
            min_tracking_confidence=tracking_confidence,
        )
        self._stabilizers: dict[str, StableCounter] = {}
        self._stable_window = stable_window

    def close(self) -> None:
        self._hands.close()

    def process(self, frame_bgr) -> tuple[Any, list[HandDetection]]:
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False
        results = self._hands.process(frame_rgb)

        detections: list[HandDetection] = []
        if not results.multi_hand_landmarks or not results.multi_handedness:
            return results, detections

        for index, hand_landmarks in enumerate(results.multi_hand_landmarks):
            classification = results.multi_handedness[index].classification[0]
            handedness = classification.label

            if self.preferred_handedness and handedness != self.preferred_handedness:
                continue

            fingers = self._get_finger_state(hand_landmarks.landmark, handedness)
            raw_count = fingers.count
            stable_count = self._stabilize(handedness, raw_count)

            detections.append(
                HandDetection(
                    handedness=handedness,
                    confidence=classification.score,
                    raw_count=raw_count,
                    stable_count=stable_count,
                    fingers=fingers,
                    landmarks=hand_landmarks,
                )
            )

        return results, detections

    def draw_landmarks(self, frame_bgr, detections: list[HandDetection]) -> None:
        for detection in detections:
            self.mp_draw.draw_landmarks(
                frame_bgr,
                detection.landmarks,
                self.mp_hands.HAND_CONNECTIONS,
                self.mp_styles.get_default_hand_landmarks_style(),
                self.mp_styles.get_default_hand_connections_style(),
            )

    def reset_stability(self) -> None:
        for stabilizer in self._stabilizers.values():
            stabilizer.clear()

    def _stabilize(self, handedness: str, value: int) -> int:
        stabilizer = self._stabilizers.setdefault(
            handedness,
            StableCounter(window_size=self._stable_window),
        )
        return stabilizer.update(value)

    def _get_finger_state(self, landmarks, handedness: str) -> FingerState:
        return FingerState(
            thumb=self._is_thumb_up(landmarks, handedness),
            index=self._is_finger_up(landmarks, "index"),
            middle=self._is_finger_up(landmarks, "middle"),
            ring=self._is_finger_up(landmarks, "ring"),
            pinky=self._is_finger_up(landmarks, "pinky"),
        )

    def _is_finger_up(self, landmarks, finger_name: str) -> bool:
        tip = landmarks[self.FINGER_TIPS[finger_name]]
        pip = landmarks[self.FINGER_PIPS[finger_name]]
        mcp = landmarks[self.FINGER_MCPS[finger_name]]

        # Works best with the palm roughly facing the camera and fingers upward.
        return tip.y < pip.y and pip.y < mcp.y

    def _is_thumb_up(self, landmarks, handedness: str) -> bool:
        tip = landmarks[self.FINGER_TIPS["thumb"]]
        ip = landmarks[3]
        mcp = landmarks[2]

        mode = self.thumb_mode
        if mode == "flip":
            handedness = "Left" if handedness == "Right" else "Right"

        if handedness == "Right":
            is_sideways_open = tip.x < ip.x < mcp.x
        else:
            is_sideways_open = tip.x > ip.x > mcp.x

        is_above_wrist = tip.y < landmarks[0].y
        return is_sideways_open and is_above_wrist
