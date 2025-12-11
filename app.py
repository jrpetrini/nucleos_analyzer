#!/usr/bin/env python3
"""
Hugging Face Spaces entry point for Nucleos Analyzer.
Runs the Dash app on the required host/port for HF Spaces.
"""

from dashboard import create_app

app = create_app()
server = app.server  # For WSGI compatibility

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7860, debug=False)
