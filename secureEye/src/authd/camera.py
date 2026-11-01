"""Single-owner access to the camera, with PAM logins taking priority over management sessions."""

import enum
import threading
import time
from typing import Protocol


class CameraUse(enum.Enum):
    AUTH = "auth"  # a PAM login; pre-empts management sessions
    MANAGE = "manage"  # a GUI enrollment/test session; yields to any login


class Cancellable(Protocol):
    def cancel(self) -> None: ...


class CameraArbiter:
    """
    Grants the camera to one session at a time.

    Rules:
      - an AUTH request cancels a MANAGE holder and waits for it to release
      - an AUTH request waits behind another AUTH holder
      - a MANAGE request waits while anyone holds the camera or any AUTH request is waiting
    Holders must call release() only once they have actually let go of the device, and
    cancel() must be idempotent: a waiting AUTH request may call it more than once.
    """

    def __init__(self) -> None:
        self._cond = threading.Condition()
        self._holder: tuple[CameraUse, Cancellable] | None = None
        self._auth_waiting = 0

    def acquire(self, use: CameraUse, session: Cancellable, timeout: float) -> bool:
        """
        Wait until session may use the camera.
        :param use: what the session is for, which sets its priority
        :param session: the session that will hold the camera; cancelled if pre-empted
        :param timeout: seconds to wait before giving up
        :return: True if the camera was granted, False on timeout
        """
        deadline = time.monotonic() + max(0.0, timeout)
        with self._cond:
            if use is CameraUse.AUTH:
                self._auth_waiting += 1
            try:
                while not self._can_take(use):
                    if use is CameraUse.AUTH and self._holder[0] is CameraUse.MANAGE:
                        self._holder[1].cancel()
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        return False
                    self._cond.wait(remaining)
                self._holder = (use, session)
                return True
            finally:
                if use is CameraUse.AUTH:
                    self._auth_waiting -= 1
                    # a MANAGE waiter may have been held back only by this request
                    self._cond.notify_all()

    def release(self, session: Cancellable) -> None:
        """
        Give the camera back. A no-op unless session is the current holder.
        :param session: the session releasing the camera
        :return: None
        """
        with self._cond:
            if self._holder is not None and self._holder[1] is session:
                self._holder = None
                self._cond.notify_all()

    def holder(self) -> CameraUse | None:
        """
        :return: what the camera is currently used for, or None if it is free
        """
        with self._cond:
            return self._holder[0] if self._holder is not None else None

    def _can_take(self, use: CameraUse) -> bool:
        if self._holder is not None:
            return False
        # AUTH requests count themselves in _auth_waiting, so only MANAGE checks it
        return use is CameraUse.AUTH or self._auth_waiting == 0
