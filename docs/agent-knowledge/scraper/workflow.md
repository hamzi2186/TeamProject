# Scraper Engine workflow

1. A user submits a public website or a lead supplies one.
2. T Rex normalizes scheme, hostname, default port, path, fragment, and tracking parameters.
3. The platform reuses the same tenant's matching Client KB when one already exists.
4. A Celery worker checks robots and sitemaps, then follows safe same-site links within configured limits.
5. Main page text and source metadata are extracted. Scripts, styles, empty pages, and duplicate content are skipped.
6. Text is split deterministically at structural boundaries with overlap.
7. TPI creates passage embeddings. Jina is the primary provider.
8. Pages, chunks, embedding metadata, and vectors are stored together.
9. The KB becomes Ready only after indexing succeeds.
10. Retrieval embeds questions as queries and searches only the authorized tenant and KB.

