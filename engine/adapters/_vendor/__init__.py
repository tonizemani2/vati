"""Vendored, orca-derived code — the ONLY place it lives (CONSTITUTION rule 6).

Nothing here is edited after vendoring beyond the documented strip (remove cross-repo
imports / path machinery, inline the constants it needs). Vendored modules NEVER read
another repo's `.env` and have no filesystem-walk logic. Our own typed wrappers live one
level up in `engine/adapters/` and import from here.
"""
