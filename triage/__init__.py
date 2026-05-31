"""Paper Triage backend.

A small FastAPI service that lets the single user triage papers surfaced by
the existing ``content_screening`` pipeline, routing decisions into Zotero and
Obsidian. It shares the screening SQLite database and ORM directly rather than
duplicating any data-access code.
"""
