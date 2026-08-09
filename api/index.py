"""Vercel serverless entry for New Vision Academy (Flask)."""
import os
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("VERCEL", "1")
os.environ.setdefault("FLASK_ENV", "production")

from app import create_app

_flask_app = create_app("production")


class _VercelPathMiddleware:
    """
    Normalize PATH_INFO for Vercel rewrites.
    With destination /api/index the function may see PATH_INFO as original
    path or as /api/index. Also handle legacy /api/$1 style.
    """

    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        path = environ.get("PATH_INFO") or "/"
        # Strip /api prefix from rewrite (legacy /api/$1)
        if path == "/api" or path == "/api/":
            environ["PATH_INFO"] = "/"
        elif path.startswith("/api/") and not path.startswith("/api/index"):
            # /api/about -> /about  (but keep /api/index as is? no)
            stripped = path[4:] or "/"
            if stripped not in ("/index", "/index.py"):
                environ["PATH_INFO"] = stripped
        # Bare function mount
        if path in ("/index", "/index.py", "/api/index", "/api/index.py"):
            environ["PATH_INFO"] = "/"
        environ["SCRIPT_NAME"] = ""
        return self.app(environ, start_response)


app = _VercelPathMiddleware(_flask_app)
