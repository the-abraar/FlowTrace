import os
import tempfile
os.environ["INGEST_API_KEY"] = "test-ingest"
os.environ.pop("READ_API_KEY", None)
os.environ.pop("DEBUG", None)
# Before any test module imports config: otherwise the first one to do so binds the real ./flowtrace.db
os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{tempfile.mkdtemp()}/test.db"
