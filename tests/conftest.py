"""Tests run isolated from real infrastructure: no Postgres (in-memory checkpointer) and the
backend in dev mode (no signature required). Set before any app module loads .env, since
load_dotenv never overrides variables that already exist. Tests that need a secret set it
explicitly (see test_security.py)."""

import os

os.environ["DATABASE_URL"] = ""
os.environ["CHIRON_BACKEND_SECRET"] = ""
