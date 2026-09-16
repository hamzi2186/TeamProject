import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("TPI_INTERNAL_SERVICE_TOKEN", "test-tpi-token")
os.environ.setdefault("AGENT_INTERNAL_SERVICE_TOKEN", "test-agent-token")
os.environ.setdefault("AUTH_JWKS_URL", "http://localhost:8000/.well-known/jwks.json")

