from __future__ import annotations

import atexit
import os
import subprocess
import time
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class OpenPoseServiceConfig:
    python_exe: str = "python"
    server_script: str = "openpose_http_server.py"   # repo root
    url: str = "http://127.0.0.1:9001/openpose"
    openpose_bin: Optional[str] = None               # set OPENPOSE_BIN env if needed
    startup_timeout_s: float = 10.0


class OpenPoseService:
    def __init__(self, cfg: OpenPoseServiceConfig):
        self.cfg = cfg
        self.proc: Optional[subprocess.Popen] = None

    def _is_up(self) -> bool:
        try:
            r = requests.post(self.cfg.url, json={"image_b64_jpg": ""}, timeout=0.5)
            # this will 500 because empty input, but server reachable => good
            return True
        except Exception:
            return False

    def start(self) -> None:
        # If already up (maybe user started it), do nothing.
        if self._is_up():
            return

        env = os.environ.copy()
        if self.cfg.openpose_bin:
            env["OPENPOSE_BIN"] = self.cfg.openpose_bin

        # start server
        self.proc = subprocess.Popen(
            [self.cfg.python_exe, self.cfg.server_script],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # wait until up
        t0 = time.time()
# sourcery skip: while-guard-to-condition
        while time.time() - t0 < self.cfg.startup_timeout_s:
            if self._is_up():
                break
            time.sleep(0.25)

        if not self._is_up():
            self.stop()
            raise RuntimeError("OpenPose HTTP server failed to start (check OPENPOSE_BIN and server_script path).")

        atexit.register(self.stop)

    def stop(self) -> None:  # sourcery skip: use-contextlib-suppress
        if self.proc is None:
            return
        try:
            self.proc.terminate()
            self.proc.wait(timeout=2)
        except Exception:
            try:
                self.proc.kill()
            except Exception:
                pass
        finally:
            self.proc = None