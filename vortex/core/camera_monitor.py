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
        """Check if frame is dark. Returns False if frame is invalid."""
        if frame is None:
            return False
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            brightness = np.mean(gray)
            return brightness < self.dark_threshold
        except Exception as e:
            self.logger.warning(f"CameraMonitor: error processing frame: {e}")
            return False

    def _run(self, camera_index):
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            self.logger.error("CameraMonitor: unable to open webcam.")
            return

        dark_count = 0
        consecutive_failures = 0
        max_failures = 10  # After this many consecutive failures, consider camera unavailable

        while self.running:
            try:
                ret, frame = cap.read()
                
                # Check if read was successful and frame is valid
                if not ret or frame is None:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        self.logger.error("CameraMonitor: camera appears unavailable after multiple read failures.")
                        # Treat as blocked if we can't read frames
                        if not self.blocked_state:
                            self.blocked_state = True
                            self.callback_on_blocked()
                    time.sleep(0.1)
                    continue
                
                # Reset failure counter on successful read
                consecutive_failures = 0
                
                # Check if frame is dark
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

            except Exception as e:
                self.logger.error(f"CameraMonitor: error reading from camera: {e}")
                consecutive_failures += 1
                if consecutive_failures >= max_failures:
                    self.logger.error("CameraMonitor: camera appears unavailable after multiple errors.")
                    if not self.blocked_state:
                        self.blocked_state = True
                        self.callback_on_blocked()
                time.sleep(0.1)
                continue

            time.sleep(0.2)

        try:
            cap.release()
        except Exception as e:
            self.logger.warning(f"CameraMonitor: error releasing camera: {e}")
        self.logger.info("CameraMonitor stopped.")
