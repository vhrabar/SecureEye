# SecureEye Auth IPC Protocol v2: management

v2 lets the GUI list and remove face models, enroll new ones and test recognition through `secureeye-authd`. Only the
daemon can run detection and hold the camera, so enrollment and testing run as daemon-side sessions that stream their
progress to the client.

v1 (`docs/auth-protocol-v1.md`) is unchanged and still serves PAM. The daemon picks the protocol from the `v` field of
the first frame on a connection.

## 1. Transport

- Same socket and framing as v1: a 4-byte big-endian length, then a UTF-8 JSON object.
- Client frames: at most `4096` bytes. Daemon frames: at most `65536` bytes, since `frame` events may carry a preview.
- One request per connection. The client sends a request; the daemon answers with zero or more events and then exactly
  one `result`, and closes the connection.
- The client must send its request within 1 s of connecting, and keep reading: a daemon write that blocks for more than
  1 s ends the session.

## 2. Authorization

The daemon reads the client's uid with `SO_PEERCRED`. Root may manage any user. Every other uid may only manage the
user it belongs to. Anything else gets `result: "forbidden"`.

Model files belong to the `secureeye` user. The daemon writes them itself, so the GUI needs no `pkexec`.

## 3. Requests

Every request carries:

| field        | type   | rules                    |
|--------------|--------|--------------------------|
| `v`          | int    | `2`                      |
| `type`       | string | one of the types below   |
| `request_id` | string | 1..64, echoed in replies |
| `username`   | string | 1..64, whose models      |

| `type`          | extra fields                                                                             |
|-----------------|------------------------------------------------------------------------------------------|
| `models_list`   | none                                                                                     |
| `models_remove` | `model` (int ≥ 0): the model id from `models_list`                                       |
| `models_clear`  | none                                                                                     |
| `enroll`        | `label` (string 1..64), `replace` (bool, default false), `preview` (bool, default false) |
| `test`          | `duration_ms` (int 1000..60000, default 15000), `preview` (bool, default false)          |

`replace: true` re-enrolls: it replaces the user's models from the active recognizer and keeps the others, like
`secureEye re-enroll`.

While an `enroll` or `test` session runs, the client may send `{"v": 2, "type": "cancel"}`. Closing the connection
also cancels it; either way the camera is released within about 200 ms.

## 4. Events

Every daemon message carries `"v": 2` and the request's `request_id`.

`started`: the session got the camera and opened it.

```json
{"v": 2, "type": "started", "request_id": "r1"}
```

`frame`: one per camera frame read.

```json
{
  "v": 2,
  "type": "frame",
  "request_id": "r1",
  "report": {
    "index": 7,
    "elapsed": 0.412,
    "state": "match",
    "darkness": 12.5,
    "dark_threshold": 60.0,
    "faces": [[0.31, 0.22, 0.28, 0.37]],
    "distance": 2.81,
    "certainty": 3.5
  },
  "preview": "<base64 JPEG>"
}
```

- `state`: `black` (unusable read, e.g. IR emitter off), `dark` (over `dark_threshold`, not searched), `no_face`,
  `multiple`, `face` (one face, not matched) or `match`. Enrollment never reports `match`.
- `faces`: `[x, y, width, height]` boxes as fractions (0..1) of the frame, so they can be drawn over a preview of any
  size.
- `distance`: the closest match in this frame, on the `[video] certainty` scale from config.ini; a match is
  `distance <= certainty`. `null` when nothing was compared, and always `null` during enrollment.
- `preview`: only when the request set `preview: true`, at most every 100 ms, a JPEG no wider than 320 px. Frames in
  between have no `preview`. The boxes in `faces` refer to the previewed image.

## 5. Results

```json
{"v": 2, "type": "result", "request_id": "r1", "result": "success", "data": {}}
```

`data` is present where listed below.

Any request may end with:

| `result`          | meaning                                                                  |
|-------------------|--------------------------------------------------------------------------|
| `invalid_request` | the request failed validation (`request_id` is `null` if it was invalid) |
| `forbidden`       | the client may not manage this user                                      |
| `busy`            | the camera or the model files stayed in use for 5 s                      |
| `internal_error`  | the daemon failed; details are in the journal                            |

`models_list`: `success` with `{"user": "...", "models": [{"id", "label", "time", "model_id"}]}` (the same shape as
`secureEye list --json`; an empty list when the user has no models), or `model_file_invalid`.

`models_remove`: `success` with `{"removed": <id>, "remaining": <count>}`, `no_models`, `model_not_found` or
`model_file_invalid`. Removing the last model deletes the file.

`models_clear`: `success` with `{"removed": <count>}` or `no_models`. It also removes a model file that cannot be read.

`enroll`: data is always `{"valid_frames", "dark_tries", "avg_darkness"}`. On `success` it also has `model` (the new
id), `label` and `model_id`. The other results are `no_face`, `multiple_faces`, `too_dark`, `black_frames`,
`model_mismatch` (the configured recognizer cannot produce models for the active embedding space), `invalid_device`,
`cancelled` and `preempted`. Nothing is written unless the result is `success`.

`test`: `completed` (ran for `duration_ms`) or `cancelled` / `preempted`, with
`{"frames", "matched_frames", "best_distance"}`. Also `no_models`, `model_mismatch` (the models are from another
recognizer; re-enroll) and `invalid_device`.

## 6. Priority over the camera

PAM logins always win. A login that needs the camera while a management session holds it cancels that session, which
then ends with `result: "preempted"`; the login waits only until the camera is released. A management request that
arrives while a login runs, or is waiting, waits up to 5 s and then gets `busy`. Only one session holds the camera at a
time.
