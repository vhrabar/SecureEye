# PAM Behavior Matrix

## A. Existing pre-check behavior in PAM (`check_enabled`)

| Condition                | Current Source              | PAM Return             |
|--------------------------|-----------------------------|------------------------|
| `core.disabled = true`   | `secureEye/src/pam/main.cc` | `PAM_AUTHINFO_UNAVAIL` |
| SSH environment detected | `secureEye/src/pam/main.cc` | `PAM_AUTHINFO_UNAVAIL` |
| Lid closed               | `secureEye/src/pam/main.cc` | `PAM_AUTHINFO_UNAVAIL` |
| No user model file       | `secureEye/src/pam/main.cc` | `PAM_AUTHINFO_UNAVAIL` |

These pre-check outcomes remain unchanged in daemon architecture.

## B. Daemon response mapping

| authd `result_code` | Meaning                       | PAM Return     |
|---------------------|-------------------------------|----------------|
| `0`                 | success                       | `PAM_SUCCESS`  |
| `10`                | no face model                 | `PAM_AUTH_ERR` |
| `11`                | timeout reached               | `PAM_AUTH_ERR` |
| `12`                | abort                         | `PAM_AUTH_ERR` |
| `13`                | too dark                      | `PAM_AUTH_ERR` |
| `14`                | invalid device                | `PAM_AUTH_ERR` |
| `15`                | rubberstamp failure           | `PAM_AUTH_ERR` |
| `99`                | authd internal/protocol error | `PAM_AUTH_ERR` |

## C. Daemon-unreachable policy (explicit decision)

Fail closed:

- connect to socket fails -> `PAM_AUTH_ERR`
- send/receive fails -> `PAM_AUTH_ERR`
- IPC timeout expires -> `PAM_AUTH_ERR`
- response parse/version check fails -> `PAM_AUTH_ERR`

