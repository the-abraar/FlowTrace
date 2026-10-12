import os
os.environ["INGEST_API_KEY"] = "test-ingest"
os.environ.pop("READ_API_KEY", None)
os.environ.pop("DEBUG", None)
