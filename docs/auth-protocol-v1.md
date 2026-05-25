# SecureEye Auth IPC Protocol v1

This document defines the IPC contract between the PAM module (`pam_secureEye.so`) and the authentication daemon (
`secureeye-authd`).

## 1. Scope

- Transport: Unix domain socket (`AF_UNIX`, `SOCK_STREAM`)
- Direction: PAM client -> auth daemon (single request, single response)
- Versioning: strict `v = 1`

Any protocol mismatch is treated as an authentication failure (`PAM_AUTH_ERR`) on the PAM side.

## 2. Socket and ownership

- Path: `/run/secureeye/authd.sock`
- Daemon owner/group: `root:secureeye`
- Socket mode: `0660`
- Only authorized peers may connect.

## 3. Framing

Each message frame uses a fixed binary header followed by UTF-8 JSON payload.

- Header: 4-byte unsigned integer, network byte order (big-endian)
- Body: exactly `length` bytes of UTF-8 JSON
- Maximum payload size: `4096` bytes

Validation rules:

1. `length` must be `1..4096`
2. Body must be valid UTF-8
3. Body must decode as valid JSON object
4. Required fields must be present and valid

Any validation failure returns `result_code = 99` from daemon when possible; if framing is broken at transport level,
PAM maps it to `PAM_AUTH_ERR`.

## 4. Request schema

```json
{
  "v": 1,
  "type": "auth_request",
  "request_id": "1fd52e2f6e9f4d16a4f4d50f3d8e3d54",
  "username": "alice",
  "service": "sudo",
  "tty": "/dev/pts/2",
  "rhost": "",
  "deadline_ms": 2500
}
```

Field rules:

- `v` (int): must be `1`
- `type` (string): must be `"auth_request"`
- `request_id` (string, 1..64)
- `username` (string, 1..64)
- `service` (string, 0..64)
- `tty` (string, 0..128)
- `rhost` (string, 0..256)
- `deadline_ms` (int, 100..30000)

Unknown fields are ignored in v1.

## 5. Response schema

```json
{
  "v": 1,
  "type": "auth_response",
  "request_id": "1fd52e2f6e9f4d16a4f4d50f3d8e3d54",
  "result_code": 0,
  "detail": "ok"
}
```

Field rules:

- `v` (int): must be `1`
- `type` (string): must be `"auth_response"`
- `request_id` (string): must equal request `request_id`
- `result_code` (int): one of defined values below
- `detail` (string, 0..512): optional operator-facing detail

## 6. Result codes

Result code values align with existing compare exit statuses in `secureEye/src/pam/main.hh` where available.

- `0` -> SUCCESS
- `10` -> NO_FACE_MODEL
- `11` -> TIMEOUT_REACHED
- `12` -> ABORT
- `13` -> TOO_DARK
- `14` -> INVALID_DEVICE
- `15` -> RUBBERSTAMP
- `99` -> AUTHD_INTERNAL_ERROR (protocol/runtime/internal daemon error)

## 7. PAM mapping rules

PAM must map responses as follows:

- `result_code == 0` -> `PAM_SUCCESS`
- `result_code in {10,11,12,13,14,15,99}` -> `PAM_AUTH_ERR`

PAM transport/protocol failures are fail-closed per project policy:

- connect failure -> `PAM_AUTH_ERR`
- write/read timeout -> `PAM_AUTH_ERR`
- malformed response -> `PAM_AUTH_ERR`
- version mismatch -> `PAM_AUTH_ERR`

## 8. Timeout contract

- PAM IPC total timeout budget: 2500 ms
- Daemon per-request execution timeout: must be less than PAM timeout (recommended 2200 ms)
- PAM retry count: 0 (single-shot)

## 9. Compatibility rules

- Any future protocol must increment `v`
- v1 clients reject non-v1 responses
- v1 daemon may ignore unknown request fields

## 10. Security notes

- Daemon must use peer credential checks (`SO_PEERCRED`) where available.
- Daemon must not trust unbounded strings; apply strict length checks before processing.
- All parser failures are non-fatal to daemon process and isolated to request scope.

