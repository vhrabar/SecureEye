import sys
import threading
import time
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[2] / "secureEye" / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from authd.camera import CameraArbiter, CameraUse  # noqa: E402


class FakeSession:
    def __init__(self, arbiter: CameraArbiter | None = None, release_on_cancel: bool = False):
        self.arbiter = arbiter
        self.release_on_cancel = release_on_cancel
        self.cancel_count = 0

    def cancel(self):
        self.cancel_count += 1
        if self.release_on_cancel:
            # release from another thread, as a worker would after closing the device
            threading.Timer(0.05, self.arbiter.release, args=(self,)).start()


def _acquire_in_thread(arbiter, use, session, timeout):
    result = {}

    def run():
        result["ok"] = arbiter.acquire(use, session, timeout)
        result["at"] = time.monotonic()

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread, result


def test_free_camera_is_granted():
    arbiter = CameraArbiter()
    session = FakeSession()
    assert arbiter.acquire(CameraUse.AUTH, session, 0)
    assert arbiter.holder() is CameraUse.AUTH
    arbiter.release(session)
    assert arbiter.holder() is None


def test_release_by_non_holder_is_ignored():
    arbiter = CameraArbiter()
    holder = FakeSession()
    assert arbiter.acquire(CameraUse.MANAGE, holder, 0)
    arbiter.release(FakeSession())
    assert arbiter.holder() is CameraUse.MANAGE


def test_auth_preempts_manage():
    arbiter = CameraArbiter()
    manage = FakeSession(arbiter, release_on_cancel=True)
    assert arbiter.acquire(CameraUse.MANAGE, manage, 0)

    auth = FakeSession()
    assert arbiter.acquire(CameraUse.AUTH, auth, 1.0)
    assert manage.cancel_count >= 1
    assert arbiter.holder() is CameraUse.AUTH


def test_auth_times_out_if_manage_never_releases():
    arbiter = CameraArbiter()
    manage = FakeSession()
    assert arbiter.acquire(CameraUse.MANAGE, manage, 0)

    start = time.monotonic()
    assert not arbiter.acquire(CameraUse.AUTH, FakeSession(), 0.2)
    assert 0.15 < time.monotonic() - start < 1.0
    assert manage.cancel_count >= 1
    assert arbiter.holder() is CameraUse.MANAGE


def test_auth_waits_for_auth_without_cancelling_it():
    arbiter = CameraArbiter()
    first = FakeSession()
    assert arbiter.acquire(CameraUse.AUTH, first, 0)

    thread, result = _acquire_in_thread(arbiter, CameraUse.AUTH, FakeSession(), 2.0)
    time.sleep(0.1)
    assert "ok" not in result
    released_at = time.monotonic()
    arbiter.release(first)
    thread.join(2)
    assert result["ok"] and result["at"] >= released_at
    assert first.cancel_count == 0


def test_manage_does_not_preempt_anyone():
    arbiter = CameraArbiter()
    auth = FakeSession()
    assert arbiter.acquire(CameraUse.AUTH, auth, 0)
    assert not arbiter.acquire(CameraUse.MANAGE, FakeSession(), 0.1)
    assert auth.cancel_count == 0

    other_manage = FakeSession()
    arbiter.release(auth)
    assert arbiter.acquire(CameraUse.MANAGE, other_manage, 0)
    assert not arbiter.acquire(CameraUse.MANAGE, FakeSession(), 0.1)
    assert other_manage.cancel_count == 0


def test_waiting_auth_beats_waiting_manage():
    arbiter = CameraArbiter()
    first = FakeSession()
    assert arbiter.acquire(CameraUse.AUTH, first, 0)

    manage_thread, manage_result = _acquire_in_thread(arbiter, CameraUse.MANAGE, FakeSession(), 2.0)
    time.sleep(0.05)
    auth_session = FakeSession()
    auth_thread, auth_result = _acquire_in_thread(arbiter, CameraUse.AUTH, auth_session, 2.0)
    time.sleep(0.05)

    arbiter.release(first)
    auth_thread.join(2)
    assert auth_result["ok"]
    time.sleep(0.05)
    assert "ok" not in manage_result

    arbiter.release(auth_session)
    manage_thread.join(2)
    assert manage_result["ok"]


def test_manage_proceeds_once_waiting_auth_gives_up():
    arbiter = CameraArbiter()
    stuck = FakeSession()
    assert arbiter.acquire(CameraUse.AUTH, stuck, 0)

    # the waiting AUTH times out first, then the camera frees up for the MANAGE waiter
    auth_thread, auth_result = _acquire_in_thread(arbiter, CameraUse.AUTH, FakeSession(), 0.1)
    manage_thread, manage_result = _acquire_in_thread(arbiter, CameraUse.MANAGE, FakeSession(), 2.0)
    auth_thread.join(2)
    assert auth_result["ok"] is False
    arbiter.release(stuck)
    manage_thread.join(2)
    assert manage_result["ok"]
