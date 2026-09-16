import os

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
os.environ.setdefault("TPI_INTERNAL_SERVICE_TOKEN", "test-tpi-token")
os.environ.setdefault("SCRAPER_INTERNAL_SERVICE_TOKEN", "test-scraper-token")
os.environ.setdefault("ENABLE_PLAYWRIGHT_FALLBACK", "false")
