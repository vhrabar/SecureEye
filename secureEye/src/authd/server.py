from .protocol import decode_frame, encode_frame, validate_auth_request, ProtocolError


class AuthdServer:
    def __init__(self, sock_path, authenticator):
        self.sock_path = sock_path
        self.authenticator = authenticator

    def _map_result(self, raw: str) -> int:
        # Normalize uncertain states to PAM-safe failure
        if raw == "ok":
            return 0
        if raw == "deny":
            return 1
        if raw == "no_model":
            return 10
        return 99  # uncached/unknown/internal

    def handle_client(self, conn):
        def read_exact(n: int) -> bytes:
            out = b""
            while len(out) < n:
                chunk = conn.recv(n - len(out))
                if not chunk:
                    raise ProtocolError("eof")
                out += chunk
            return out

        req_id = None
        try:
            req = decode_frame(read_exact)
            validate_auth_request(req)
            req_id = req["request_id"]

            raw = self.authenticator.authenticate(req)  # "ok"/"deny"/...
            code = self._map_result(raw)

            resp = {
                "v": 1,
                "type": "auth_response",
                "request_id": req_id,
                "result_code": code,
                "message": "ok" if code == 0 else "auth failed",
            }
        except Exception:
            resp = {
                "v": 1,
                "type": "auth_response",
                "request_id": req_id or "",
                "result_code": 99,
                "message": "internal error",
            }

        conn.sendall(encode_frame(resp))
