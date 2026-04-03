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

usage() {
  cat <<EOF
Usage: entrypoint-pam-sudo-smoke.sh [--help]

Environment variables:
  PAM_FLOW            smoke (default) | full | interactive
  PAM_SERVICE         PAM service file name (default: sudo)
  SECUREEYE_USER      test user (default: test_user)
  SECUREEYE_PASS      test user password (default: test_user)
  SECUREEYE_DEVICE    camera device path in container (default: /dev/video2)

Flow modes:
  smoke: build/install module + patch PAM + sudo PAM smoke check
  full : smoke + secureEye add + secureEye test
  interactive: prompt for user setup + optional add/test + interactive sudo check
EOF
}

if [[ "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

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

case "$PAM_FLOW" in
  smoke)
    ;;
  full)
    RUN_ADD=1
    RUN_TEST=1
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

if [[ ! -f "$PAM_DIR/pam_secureEye.so" ]]; then
  echo "pam_secureEye.so was not installed"
  exit 1
fi

if ! id "$SECUREEYE_USER" >/dev/null 2>&1; then
  useradd -m "$SECUREEYE_USER"
fi

echo "$SECUREEYE_USER:$SECUREEYE_PASS" | chpasswd
usermod -aG sudo "$SECUREEYE_USER"

CONFIG_PATH="/opt/secureeye/etc/howdy/config.ini"
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
  run_with_display /opt/secureeye/bin/secureEye -U "$SECUREEYE_USER" add
fi

# TODO: Implement proper GUI for test utility that amy be run inside Docker
# if [[ "$RUN_TEST" == "1" ]]; then
#  echo "Running secureEye test flow for user $SECUREEYE_USER"
#  run_with_display /opt/secureeye/bin/secureEye -U "$SECUREEYE_USER" test
# fi

# Sudo check: interactive mode uses a real prompt path, smoke/full stay non-interactive.
if [[ "$INTERACTIVE_SUDO" == "1" ]]; then
  echo "Running interactive sudo check as $SECUREEYE_USER"
  su - "$SECUREEYE_USER" -c "sudo -k id"
else
  su - "$SECUREEYE_USER" -c "echo '$SECUREEYE_PASS' | sudo -S -k id"
fi

echo "PAM flow '$PAM_FLOW' completed inside container."

