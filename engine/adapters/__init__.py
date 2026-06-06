"""Adapters — thin, typed wrappers around external tools.

Everything the engine reaches for (HTML→markdown, search, LLM, PDF, ...) goes through a
small interface here, so the rest of the code never depends on a specific library or on
orca97-v2 internals. Orca-derived code, when vendored, lives only in `adapters/_vendor/`.
"""
