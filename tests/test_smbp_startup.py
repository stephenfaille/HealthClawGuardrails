"""Guard: the SMBP table must actually be CREATED at app import time.

Production runs `gunicorn main:app` — it imports `main` (NOT the `__main__`
block). main.py's startup `db.create_all()` only creates tables whose models
are imported *before* it runs. The SMBP blueprint is registered later in main.py
and imports SMBPSession, so the table ends up in the SQLAlchemy *metadata* by the
end of import — but if it wasn't imported before `create_all()`, the table is
never physically created, and POST /r6/smbp/enroll 500s in prod (while
Observation writes still work, since R6Resource's table predates SMBP).

So this checks the ENGINE's real table list (what create_all actually built),
not the metadata, using a temp-file SQLite in a clean subprocess that mirrors
the gunicorn import path.
"""

import os
import subprocess
import sys
import tempfile


def test_smbp_table_physically_created_on_plain_import():
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False)
    tmp.close()
    code = (
        "import main;"
        "from r6.models import db;"
        "from sqlalchemy import inspect;"
        "ctx = main.app.app_context(); ctx.push();"
        "names = inspect(db.engine).get_table_names();"
        "ctx.pop();"
        "assert 'smbp_sessions' in names,"
        "  'smbp_sessions not created by startup create_all() — add"
        " import r6.smbp.models to the main.py create_all block: ' + repr(names);"
        "print('OK')"
    )
    try:
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, cwd=repo_root,
            env={**os.environ,
                 "SQLALCHEMY_DATABASE_URI": "sqlite:///" + tmp.name},
        )
    finally:
        os.unlink(tmp.name)
    assert result.returncode == 0, (
        "main import failed or smbp_sessions not physically created:\n"
        + result.stdout + result.stderr
    )
    assert "OK" in result.stdout
