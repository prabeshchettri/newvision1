"""
WSGI / Vercel entrypoint for New Vision Academy.
Vercel auto-detects `app` in wsgi.py at project root.
"""
import os
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

os.environ.setdefault("FLASK_ENV", "production")
if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
    os.environ.setdefault("VERCEL", "1")

from app import create_app

app = create_app(os.environ.get("FLASK_ENV", "production"))
