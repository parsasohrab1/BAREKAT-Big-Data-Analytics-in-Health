"""Batch encrypt existing PHI fields at rest."""

from __future__ import annotations

from sqlalchemy import text

from barekat.security.phi_crypto import encrypt_phi, is_encrypted
from barekat.storage.database import engine


def encrypt_clinical_notes(*, triggered_by: str = "system") -> dict:
    """Encrypt raw.clinical_notes.note_text in place."""
    select_q = text("SELECT note_id, note_text FROM raw.clinical_notes")
    update_q = text("UPDATE raw.clinical_notes SET note_text = :text WHERE note_id = :id")

    encrypted_count = 0
    with engine.connect() as conn:
        rows = conn.execute(select_q).fetchall()

    for note_id, note_text in rows:
        if not note_text or is_encrypted(note_text):
            continue
        enc = encrypt_phi(note_text)
        with engine.begin() as conn:
            conn.execute(update_q, {"id": note_id, "text": enc})
        encrypted_count += 1

    if encrypted_count:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO audit.phi_encryption_log
                    (table_name, column_name, records_encrypted, triggered_by)
                VALUES ('clinical_notes', 'note_text', :count, :by)
            """), {"count": encrypted_count, "by": triggered_by})

    return {"table": "clinical_notes", "encrypted": encrypted_count}
