# Scraper Engine FAQ

## Why was a website reused?

T Rex normalizes common variants such as `http`, `https`, `www`, fragments, default ports, and trailing slashes. Matching normalized sites owned by the same user reuse one KB.

## Can two customers index the same public site?

Yes. Each receives an independently owned KB. T Rex never merges Client KB ownership across tenants.

## Why is a page missing?

The page may be blocked by robots, external to the site, binary, empty, duplicate, unsafe, beyond configured limits, or unavailable during the crawl.

## Does the Scraper expose provider credentials?

No. Embedding provider credentials and provider-specific behavior stay inside TPI.

