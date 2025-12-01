# vortex/core/camera_monitor.py

import cv2
import numpy as np
import threading
import time


class CameraMonitor:
    """
    Continuously monitors webcam feed for:
    - Camera obstruction (very dark frames)

    It does NOT run face recognition; that belongs to IdentityManager.
    """

    def __init__(self, identity_manager, logger, callback_on_blocked, callback_on_restored):
        self.identity = identity_manager
        self.logger = logger
        self.callback_on_blocked = callback_on_blocked
        self.callback_on_restored = callback_on_restored

        self.running = False
        self.thread = None
        self.blocked_state = False  # True = currently considered blocked

        # Tunable thresholds
        self.dark_threshold = 60          # higher = more sensitive to dark frames
        self.dark_frames_required = 5     # how many consecutive dark frames before trigger

    def start(self, camera_index=0):
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._run, args=(camera_index,), daemon=True)
        self.thread.start()
        self.logger.info("CameraMonitor started.")

    def stop(self):
        self.running = False
        # wait briefly for the thread to exit so we can safely reopen the camera later
        if self.thread is not None and self.thread.is_alive():
            try:
                self.thread.join(timeout=1.0)
            except Exception:
                pass
        self.thread = None

    def _is_dark(self, frame):
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = np.mean(gray)
        return brightness < self.dark_threshold

    def _run(self, camera_index):
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.logger.error("CameraMonitor: unable to open webcam.")
            return

        dark_count = 0

        while self.running:
            ret, frame = cap.read()
            if not ret:
                time.sleep(0.1)
                continue

            if self._is_dark(frame):
                dark_count += 1
            else:
                dark_count = 0

            # Enter blocked state
            if dark_count >= self.dark_frames_required and not self.blocked_state:
                self.blocked_state = True
                self.logger.warning("CameraMonitor: camera appears covered/blocked.")
                self.callback_on_blocked()

            # Exit blocked state
            if dark_count == 0 and self.blocked_state:
                self.blocked_state = False
                self.logger.info("CameraMonitor: camera feed restored.")
                self.callback_on_restored()

            time.sleep(0.2)

        cap.release()
        self.logger.info("CameraMonitor stopped.")
