#!/usr/bin/env bash
# Start the PC Vision Server
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR"
"$SCRIPT_DIR/.venv/bin/python" "$SCRIPT_DIR/server/server.py"
