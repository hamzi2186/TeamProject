# Scraper Engine overview

The T Rex Scraper Engine builds a reusable Client Knowledge Base from each lead website. A knowledge base belongs to one platform user and can be shared by that user's leads whose normalized website matches. It is never shared across tenants.

The engine crawls safe same-site pages, extracts useful text, creates deterministic chunks, embeds them through the internal TPI service, and stores them in PostgreSQL with pgvector. Ready knowledge bases support source-linked semantic retrieval for Calling, SMS, and Mailer.

