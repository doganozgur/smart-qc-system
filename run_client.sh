#!/usr/bin/env bash
# Start the Desktop Inspection Application
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR"
export QT_QPA_PLATFORM_PLUGIN_PATH="$SCRIPT_DIR/.venv/lib/python3.14/site-packages/PySide6/Qt/plugins"

# Fix GNOME 47+ gsettings schema crash on Ubuntu 26.04
export QT_QPA_PLATFORMTHEME="generic"

# Auto fallback for Wayland / X11
if [ -n "$WAYLAND_DISPLAY" ]; then
    export QT_QPA_PLATFORM="wayland;xcb"
elif [ -n "$DISPLAY" ]; then
    export QT_QPA_PLATFORM="xcb"
fi

exec "$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/client/app.py" "$@"
