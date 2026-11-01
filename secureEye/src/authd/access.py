"""Who may ask the daemon to act for which user, decided by the client's SO_PEERCRED uid."""

import pwd
import socket
import struct


def peer_uid(conn: socket.socket) -> int:
    """
    Return the uid of the process on the other end of a unix socket.
    :param conn: the client connection
    :return: the uid the kernel recorded when the client connected
    """
    creds = conn.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
    _pid, uid, _gid = struct.unpack("3i", creds)
    return uid


def may_act_for(uid: int, username: str) -> bool:
    """
    Root may act for anyone; everyone else only for themselves.
    :param uid: the client's uid
    :param username: the user the client wants to authenticate or manage
    :return: whether the request is allowed
    """
    if uid == 0:
        return True
    try:
        return pwd.getpwnam(username).pw_uid == uid
    except KeyError:
        return False
