from __future__ import annotations

import argparse
import sys

import cv2

from hand_detector import HandDetector
from utils import FPSCounter


WINDOW_NAME = "Real-Time Finger Detection"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta dedos levantados en tiempo real con OpenCV y MediaPipe."
    )
    parser.add_argument("--camera", type=int, default=0, help="Indice de la camara.")
    parser.add_argument("--width", type=int, default=1280, help="Ancho deseado.")
    parser.add_argument("--height", type=int, default=720, help="Alto deseado.")
    parser.add_argument(
        "--hands",
        type=int,
        default=2,
        choices=(1, 2),
        help="Numero maximo de manos a detectar.",
    )
    parser.add_argument(
        "--dominant-hand",
        choices=("Left", "Right"),
        default=None,
        help="Filtra por mano dominante segun MediaPipe.",
    )
    parser.add_argument(
        "--no-mirror",
        action="store_true",
        help="No invierte horizontalmente la camara.",
    )
    parser.add_argument(
        "--stable-window",
        type=int,
        default=7,
        help="Frames usados para suavizar el conteo.",
    )
    parser.add_argument(
        "--thumb-mode",
        choices=("auto", "flip"),
        default="auto",
        help="Usa 'flip' si el pulgar se cuenta al reves con tu camara.",
    )
    return parser.parse_args()


def draw_overlay(frame, detections, fps: float, args: argparse.Namespace) -> None:
    height, width = frame.shape[:2]
    panel_height = 132 if args.hands == 1 else 170

    cv2.rectangle(frame, (0, 0), (width, panel_height), (20, 24, 32), -1)
    cv2.putText(
        frame,
        f"FPS: {fps:.1f}",
        (24, 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.8,
        (100, 220, 255),
        2,
        cv2.LINE_AA,
    )

    if not detections:
        cv2.putText(
            frame,
            "No se detecta mano",
            (24, 84),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (80, 150, 255),
            2,
            cv2.LINE_AA,
        )
    else:
        total = sum(detection.stable_count for detection in detections)
        label = f"Dedos detectados: {total}"
        cv2.putText(
            frame,
            label,
            (24, 86),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.2,
            (70, 255, 120),
            3,
            cv2.LINE_AA,
        )

        y = 122
        for detection in detections:
            details = (
                f"{detection.handedness} "
                f"({detection.confidence:.2f}) "
                f"estable={detection.stable_count} raw={detection.raw_count}"
            )
            cv2.putText(
                frame,
                details,
                (24, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.62,
                (230, 235, 240),
                2,
                cv2.LINE_AA,
            )
            y += 34

    controls = "Q/ESC salir | R reset estabilidad | H invertir pulgar"
    cv2.putText(
        frame,
        controls,
        (24, height - 24),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (245, 245, 245),
        2,
        cv2.LINE_AA,
    )


def open_camera(args: argparse.Namespace):
    capture = cv2.VideoCapture(args.camera)
    if not capture.isOpened():
        return None

    capture.set(cv2.CAP_PROP_FRAME_WIDTH, args.width)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, args.height)
    capture.set(cv2.CAP_PROP_FPS, 30)
    return capture


def main() -> int:
    args = parse_args()
    capture = open_camera(args)
    if capture is None:
        print(f"No se pudo abrir la camara con indice {args.camera}.", file=sys.stderr)
        return 1

    detector = HandDetector(
        max_num_hands=args.hands,
        stable_window=args.stable_window,
        preferred_handedness=args.dominant_hand,
        thumb_mode=args.thumb_mode,
    )
    fps_counter = FPSCounter()

    cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    try:
        while True:
            ok, frame = capture.read()
            if not ok:
                print("No se pudo leer un frame de la camara.", file=sys.stderr)
                return 1

            if not args.no_mirror:
                frame = cv2.flip(frame, 1)

            _, detections = detector.process(frame)
            detector.draw_landmarks(frame, detections)
            draw_overlay(frame, detections, fps_counter.update(), args)

            cv2.imshow(WINDOW_NAME, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q")):
                break
            if key == ord("r"):
                detector.reset_stability()
            if key == ord("h"):
                detector.thumb_mode = "flip" if detector.thumb_mode == "auto" else "auto"
                detector.reset_stability()
    finally:
        detector.close()
        capture.release()
        cv2.destroyAllWindows()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
