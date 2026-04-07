#!/usr/bin/env bash
set -euo pipefail

PAM_FLOW="${PAM_FLOW:-smoke}"
PAM_SERVICE="${PAM_SERVICE:-sudo}"
SECUREEYE_USER="${SECUREEYE_USER:-${TEST_USER:-test_user}}"
SECUREEYE_PASS="${SECUREEYE_PASS:-${TEST_PASS:-test_user}}"
SECUREEYE_DEVICE="${SECUREEYE_DEVICE:-${SECUREEYE_VIDEO_DEVICE:-/dev/video2}}"
RUN_ADD=0
RUN_TEST=0
INTERACTIVE_SUDO=0
AUTHD_PID=""
AUTHD_SOCKET="${AUTHD_SOCKET:-/run/secureeye/authd.sock}"
AUTHD_LOG="/tmp/secureeye-authd.log"
SE_PREFIX=""
SE_CONFIG_DIR=""
SE_MODELS_DIR=""
SE_AUTHD_MAIN=""
SE_CLI_BIN=""
DROP_TO_BASH="${PAM_DROP_TO_BASH:-0}"

usage() {
  cat <<EOF
Usage: entrypoint-pam-sudo-smoke.sh [--help]

Environment variables:
  PAM_FLOW            smoke (default) | full | interactive
  PAM_SERVICE         PAM service file name (default: sudo)
  SECUREEYE_USER      test user (default: test_user)
  SECUREEYE_PASS      test user password (default: test_user)
  SECUREEYE_DEVICE    camera device path in container (default: /dev/video2)
  PAM_DROP_TO_BASH    1 to open bash after flow completion (default: 0)

Flow modes:
  smoke: build/install module + patch PAM + sudo PAM smoke check
  full : smoke + secureEye add + secureEye test
  interactive: prompt for user setup + optional add/test + interactive sudo check
EOF
}

for arg in "$@"; do
  case "$arg" in
    --help)
      usage
      exit 0
      ;;
    --bash)
      DROP_TO_BASH=1
      ;;
    *)
      ;;
  esac
done

cd /workspace
export PYTHONPATH="/workspace/secureEye/src:${PYTHONPATH:-}"

detect_pam_dir() {
  for dir in /lib/x86_64-linux-gnu/security /lib/security /usr/lib/security; do
    if [[ -d "$dir" ]]; then
      echo "$dir"
      return 0
    fi
  done
  return 1
}

run_with_display() {
  if [[ -n "${DISPLAY:-}" ]]; then
    "$@"
    return
  fi

  if command -v xvfb-run >/dev/null 2>&1; then
    xvfb-run -a "$@"
    return
  fi

  echo "No DISPLAY and xvfb-run not installed; cannot run interactive UI command: $*"
  exit 1
}

is_tty() {
  [[ -t 0 && -t 1 ]]
}

prompt_default() {
  local prompt="$1"
  local default_val="$2"
  local out
  read -r -p "$prompt [$default_val]: " out
  echo "${out:-$default_val}"
}

prompt_yes_no() {
  local prompt="$1"
  local default_val="$2"
  local out
  read -r -p "$prompt [$default_val]: " out
  out="${out:-$default_val}"
  [[ "$out" =~ ^[Yy]$ ]]
}

run_interactive_sudo_check() {
  local user="$1"
  local sudo_cmd="sudo -k id"

  # Prefer a pty wrapper
  if command -v script >/dev/null 2>&1; then
    if su - "$user" -c "script -q -c \"$sudo_cmd\" /dev/null"; then
      return
    fi
  fi

  if is_tty; then
    if su - "$user" -c "$sudo_cmd"; then
      return
    fi
  fi

  # Last-resort fallback for CI/containers with no usable tty.
  su - "$user" -c "echo '$SECUREEYE_PASS' | sudo -S -k id"
}

meson_opt() {
  local builddir="$1"
  local optname="$2"
  "$PYTHON_BIN" - <<'PY' "$builddir" "$optname"
import json
import subprocess
import sys

builddir = sys.argv[1]
name = sys.argv[2]
out = subprocess.check_output(["meson", "introspect", builddir, "--buildoptions"], text=True)
for item in json.loads(out):
    if item.get("name") == name:
        val = item.get("value")
        if isinstance(val, bool):
            print("true" if val else "false")
        else:
            print(val)
        break
PY
}

discover_install_paths() {
  local prefix="$1"

  SE_AUTHD_MAIN="$(find "$prefix" -type f -path '*/secureEye/authd/main.py' | head -n 1 || true)"
  SE_CLI_BIN="$(find "$prefix" -type f -path '*/bin/secureEye' | head -n 1 || true)"

  if [[ -z "$SE_AUTHD_MAIN" ]]; then
    echo "Could not find installed authd entrypoint under prefix: $prefix"
    find "$prefix" -maxdepth 6 -type d -name secureEye 2>/dev/null || true
    exit 1
  fi

  if [[ -z "$SE_CLI_BIN" ]]; then
    echo "Could not find installed secureEye launcher under prefix: $prefix"
    exit 1
  fi
}

start_authd() {
  local authd_root
  authd_root="$(dirname "$(dirname "$SE_AUTHD_MAIN")")"

  echo "Starting authd daemon ($SE_AUTHD_MAIN)"
  : > "$AUTHD_LOG"
  SECUREEYE_AUTHD_SOCKET="$AUTHD_SOCKET" \
    PYTHONPATH="$authd_root:${PYTHONPATH:-}" \
    "$PYTHON_BIN" "$SE_AUTHD_MAIN" >>"$AUTHD_LOG" 2>&1 &
  AUTHD_PID=$!

  for _ in $(seq 1 50); do
    [[ -S "$AUTHD_SOCKET" ]] && return
    sleep 0.1
  done

  echo "authd did not create socket at $AUTHD_SOCKET"
  echo "--- authd log ---"
  cat "$AUTHD_LOG" || true
  exit 1
}

stop_authd() {
  if [[ -n "$AUTHD_PID" ]] && kill -0 "$AUTHD_PID" >/dev/null 2>&1; then
    kill "$AUTHD_PID" >/dev/null 2>&1 || true
    wait "$AUTHD_PID" >/dev/null 2>&1 || true
  fi
}

require_model() {
  local model_path="$SE_MODELS_DIR/${SECUREEYE_USER}.dat"
  if [[ ! -f "$model_path" ]]; then
    echo "Face model not found for user '$SECUREEYE_USER': $model_path"
    echo "Run flow with PAM_FLOW=full or PAM_FLOW=interactive and perform 'secureEye add'."
    exit 1
  fi
}

has_model() {
  [[ -f "$SE_MODELS_DIR/${SECUREEYE_USER}.dat" ]]
}

case "$PAM_FLOW" in
  smoke)
    ;;
  full)
    RUN_ADD=1
    RUN_TEST=1
    DROP_TO_BASH=1
    ;;
  interactive)
    if ! is_tty; then
      echo "PAM_FLOW=interactive requires an interactive TTY (use 'docker compose run')."
      exit 1
    fi
    SECUREEYE_USER="$(prompt_default "SecureEye test user" "$SECUREEYE_USER")"
    SECUREEYE_PASS="$(prompt_default "Password for $SECUREEYE_USER" "$SECUREEYE_PASS")"
    SECUREEYE_DEVICE="$(prompt_default "Camera device in container" "$SECUREEYE_DEVICE")"
    if prompt_yes_no "Run secureEye add now?" "Y"; then
      RUN_ADD=1
    fi
    if prompt_yes_no "Run secureEye test now?" "Y"; then
      RUN_TEST=1
    fi
    INTERACTIVE_SUDO=1
    ;;
  *)
    echo "Unsupported PAM_FLOW '$PAM_FLOW'. Use smoke, full, or interactive."
    exit 1
    ;;
esac

echo "Flow selection: PAM_FLOW=$PAM_FLOW RUN_ADD=$RUN_ADD RUN_TEST=$RUN_TEST USER=$SECUREEYE_USER"

PAM_DIR="$(detect_pam_dir || true)"
if [[ -z "$PAM_DIR" ]]; then
  echo "Could not detect a PAM module directory in container"
  exit 1
fi

echo "Using PAM module directory: $PAM_DIR"
PYTHON_BIN="$(command -v python3 || true)"
if [[ -z "$PYTHON_BIN" ]]; then
  echo "python3 not found in container PATH"
  exit 1
fi

meson setup --wipe /tmp/build-pam /workspace \
  --prefix /opt/secureeye \
  -Dpam_dir="$PAM_DIR" \
  -Dconfig_dir=/opt/secureeye/etc/howdy \
  -Duser_models_dir=/opt/secureeye/etc/howdy/models \
  -Dpython_path="$PYTHON_BIN" \
  -Dinstall_pam_config=false
meson compile -C /tmp/build-pam
meson install -C /tmp/build-pam

SE_PREFIX="$(meson_opt /tmp/build-pam prefix)"
SE_CONFIG_DIR="$(meson_opt /tmp/build-pam config_dir)"
SE_MODELS_DIR="$(meson_opt /tmp/build-pam user_models_dir)"

discover_install_paths "$SE_PREFIX"
start_authd
trap stop_authd EXIT

if [[ ! -f "$PAM_DIR/pam_secureEye.so" ]]; then
  echo "pam_secureEye.so was not installed"
  exit 1
fi

if ! id "$SECUREEYE_USER" >/dev/null 2>&1; then
  useradd -m "$SECUREEYE_USER"
fi

echo "$SECUREEYE_USER:$SECUREEYE_PASS" | chpasswd
usermod -aG sudo "$SECUREEYE_USER"

CONFIG_PATH="$SE_CONFIG_DIR/config.ini"
if [[ -f "$CONFIG_PATH" ]]; then
  sed -i "s|^device_path = .*|device_path = $SECUREEYE_DEVICE|" "$CONFIG_PATH"
fi

PAM_FILE="/etc/pam.d/$PAM_SERVICE"
if [[ ! -f "$PAM_FILE" ]]; then
  echo "PAM file not found: $PAM_FILE"
  exit 1
fi

cp "$PAM_FILE" "$PAM_FILE.bak"
{
  echo "auth sufficient pam_secureEye.so"
  cat "$PAM_FILE.bak"
} > "$PAM_FILE"

if [[ "$RUN_ADD" == "1" ]]; then
  echo "Running secureEye add flow for user $SECUREEYE_USER"
  run_with_display "$SE_CLI_BIN" -U "$SECUREEYE_USER" add
fi

# If test was requested without add and no model exists, enroll automatically.
if [[ "$RUN_TEST" == "1" && "$RUN_ADD" == "0" ]] && ! has_model; then
  echo "No face model found for $SECUREEYE_USER; running secureEye add before test"
  run_with_display "$SE_CLI_BIN" -U "$SECUREEYE_USER" add
fi

if [[ "$RUN_ADD" == "1" || "$RUN_TEST" == "1" ]]; then
  require_model
fi

if [[ "$RUN_TEST" == "1" ]]; then
  echo "Running secureEye test flow for user $SECUREEYE_USER"
  run_with_display "$SE_CLI_BIN" -U "$SECUREEYE_USER" test
fi

# Sudo check: interactive mode uses a real prompt path, smoke/full stay non-interactive.
if [[ "$INTERACTIVE_SUDO" == "1" ]]; then
  echo "Running interactive sudo check as $SECUREEYE_USER"
  run_interactive_sudo_check "$SECUREEYE_USER"
else
  su - "$SECUREEYE_USER" -c "echo '$SECUREEYE_PASS' | sudo -S -k id"
fi

echo "PAM flow '$PAM_FLOW' completed inside container."

if [[ "$DROP_TO_BASH" == "1" ]]; then
  echo "Opening bash shell (DROP_TO_BASH=1)."
  exec bash
fi

