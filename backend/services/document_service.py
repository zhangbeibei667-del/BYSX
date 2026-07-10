from pathlib import Path

from fastapi import UploadFile

from backend.db.database import DATA_DIR, get_connection


class DocumentService:
    def __init__(self) -> None:
        self.upload_dir = DATA_DIR / "documents"
        self.upload_dir.mkdir(parents=True, exist_ok=True)

    def create_document(self, title: str, source: str = "", content: str = "", file_path: str = "") -> dict:
        with get_connection() as conn:
            cursor = conn.execute(
                """
                INSERT INTO documents (title, source, content, file_path)
                VALUES (?, ?, ?, ?)
                """,
                (title, source, content, file_path),
            )
            conn.commit()
            doc_id = int(cursor.lastrowid)
        return self.get_document(doc_id) or {"id": doc_id}

    async def upload_document(self, file: UploadFile, source: str = "") -> dict:
        safe_name = Path(file.filename or "uploaded_document").name
        target = self.upload_dir / safe_name
        content_bytes = await file.read()
        target.write_bytes(content_bytes)

        text_preview = ""
        try:
            text_preview = content_bytes[:2000].decode("utf-8")
        except UnicodeDecodeError:
            text_preview = "Binary document uploaded. Text preview is not available in mock mode."

        return self.create_document(
            title=safe_name,
            source=source,
            content=text_preview,
            file_path=str(target),
        )

    def list_documents(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                """
                SELECT id, title, source, content, file_path, created_at
                FROM documents
                ORDER BY id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: int) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                """
                SELECT id, title, source, content, file_path, created_at
                FROM documents
                WHERE id = ?
                """,
                (document_id,),
            ).fetchone()
        return dict(row) if row else None

    def update_document(
        self,
        document_id: int,
        title: str | None = None,
        source: str | None = None,
        content: str | None = None,
    ) -> dict | None:
        old = self.get_document(document_id)
        if old is None:
            return None

        new_title = title if title is not None else old["title"]
        new_source = source if source is not None else old["source"]
        new_content = content if content is not None else old["content"]

        with get_connection() as conn:
            conn.execute(
                """
                UPDATE documents
                SET title = ?, source = ?, content = ?
                WHERE id = ?
                """,
                (new_title, new_source, new_content, document_id),
            )
            conn.commit()
        return self.get_document(document_id)

    def delete_document(self, document_id: int) -> bool:
        old = self.get_document(document_id)
        if old is None:
            return False

        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()

        file_path = old.get("file_path")
        if file_path:
            path = Path(file_path)
            if path.exists() and path.is_file() and self.upload_dir in path.parents:
                path.unlink()
        return cursor.rowcount > 0
