#!/usr/bin/env bash
# Start the Desktop Inspection Application
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/client/app.py"
