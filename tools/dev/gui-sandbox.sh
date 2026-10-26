#!/usr/bin/env bash
# Run the GUI against a development secureeye-authd, both from this checkout, in the .devroot sandbox.
#
# The dev daemon runs as you, from secureEye/src, on its own socket, with config and face models from
# .devroot/etc/secureEye. The installed daemon, /etc/secureEye and /etc/pam.d are never touched:
#   - the GUI talks to the dev socket (SECUREEYE_AUTHD_SOCKET)
#   - the Configuration page reads .devroot's config.ini (SECUREEYE_CONFIG)
#   - saving the configuration and the face login switch run the installed CLI through pkexec, which drops
#     these variables and would write to /etc; SECUREEYE_CLI_PATH points nowhere, so they fail instead
# The dashboard's daemon card and Start/Stop still show and control the installed systemd service.
#
#   tools/dev/gui-sandbox.sh            build the GUI, start the dev daemon, run the GUI; Ctrl+C or closing the
#                                       GUI stops the daemon
#   BUILD_DIR=build-dev tools/dev/gui-sandbox.sh
#
# The camera is the one in .devroot's config.ini (device_path); /dev/video* grant your session access.

set -euo pipefail

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DEVROOT=$ROOT/.devroot
BUILD_DIR=${BUILD_DIR:-$ROOT/build}
# unix socket paths are limited to 108 bytes
RUN_DIR=${XDG_RUNTIME_DIR:-/tmp}/secureeye-dev
SOCKET=$RUN_DIR/authd.sock
PYTHON=$ROOT/.venv/bin/python

if [[ ! -f $DEVROOT/etc/secureEye/config.ini ]]; then
    mkdir -p "$DEVROOT/etc/secureEye/models" "$DEVROOT/var/log/secureEye"
    cp "$ROOT/secureEye/src/config.ini" "$DEVROOT/etc/secureEye/config.ini"
    echo "Created $DEVROOT/etc/secureEye/config.ini from the shipped config; set device_path in it."
fi

export SECUREEYE_CONFIG_DIR=$DEVROOT/etc/secureEye
export SECUREEYE_MODELS_DIR=$DEVROOT/etc/secureEye/models
export SECUREEYE_LOG_PATH=$DEVROOT/var/log/secureEye
export SECUREEYE_AUTHD_SOCKET=$SOCKET
if [[ -z ${SECUREEYE_DLIB_DATA_DIR:-} && -d /usr/share/dlib-data ]]; then
    export SECUREEYE_DLIB_DATA_DIR=/usr/share/dlib-data
fi

meson compile -C "$BUILD_DIR" secureEye/src/gui/secureeye-gui

mkdir -p "$RUN_DIR"
rm -f "$SOCKET"
PYTHONPATH=$ROOT/secureEye/src "$PYTHON" "$ROOT/secureEye/src/authd/main.py" &
DAEMON=$!
trap 'kill "$DAEMON" 2>/dev/null; wait "$DAEMON" 2>/dev/null; rm -f "$SOCKET"' EXIT

for _ in $(seq 100); do
    [[ -S $SOCKET ]] && break
    kill -0 "$DAEMON" 2>/dev/null || { echo "dev daemon exited; see its output above" >&2; exit 1; }
    sleep 0.2
done
[[ -S $SOCKET ]] || { echo "dev daemon did not open $SOCKET" >&2; exit 1; }

echo "dev daemon pid $DAEMON on $SOCKET"
echo "config: $SECUREEYE_CONFIG_DIR/config.ini"
echo "models: $SECUREEYE_MODELS_DIR"

SECUREEYE_CONFIG=$SECUREEYE_CONFIG_DIR/config.ini \
    SECUREEYE_CLI_PATH=/nonexistent/secureEye-sandbox \
    "$BUILD_DIR/secureEye/src/gui/secureeye-gui"
