"""Redacted database configuration and DNS diagnostic."""
from __future__ import annotations

import re
import socket
import sys
from pathlib import Path

from sqlalchemy.engine import make_url

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402, I001


url = make_url(get_settings().database_url)
print(f"driver={url.drivername}")
print(f"host_present={bool(url.host)}")
print(f"port={url.port}")
print(f"username_present={bool(url.username)}")
print(f"password_present={bool(url.password)}")
print(f"host_is_supabase={bool(url.host and 'supabase.' in url.host)}")
print(f"host_ends_supabase_com={bool(url.host and url.host.endswith('.supabase.com'))}")
print(f"host_ends_supabase_co={bool(url.host and url.host.endswith('.supabase.co'))}")
pooler_pattern = r"^aws-\d+-[a-z]+-[a-z]+-\d+\.pooler\.supabase\.com$"
print(f"host_matches_pooler_pattern={bool(url.host and re.fullmatch(pooler_pattern, url.host))}")
print(f"host_ends_pooler_supabase={bool(url.host and url.host.endswith('.pooler.supabase.com'))}")
print(f"host_starts_aws={bool(url.host and url.host.startswith('aws-'))}")
print(f"host_label_count={len(url.host.split('.')) if url.host else 0}")
print(f"host_has_whitespace={bool(url.host and any(char.isspace() for char in url.host))}")
try:
    socket.getaddrinfo(url.host, url.port)
except OSError as error:
    print("dns_resolves=False")
    print(f"dns_error_type={type(error).__name__}")
else:
    print("dns_resolves=True")
