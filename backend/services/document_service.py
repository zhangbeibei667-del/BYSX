from pathlib import Path
import json
import zipfile
from xml.etree import ElementTree

from fastapi import UploadFile

from backend.db.database import DATA_DIR, get_connection
from backend.services.vector_retrieval_service import VectorRetrievalService


METADATA_FIELDS = ("category", "edition", "chapter", "section", "publisher", "identifier", "source_url", "license")


class DocumentService:
    def __init__(self) -> None:
        self.upload_dir = DATA_DIR / "documents"
        self.upload_dir.mkdir(parents=True, exist_ok=True)
        self.vector = VectorRetrievalService()

    def create_document(self, title: str, source: str = "", content: str = "", file_path: str = "", **metadata) -> dict:
        values = [metadata.get(field, "未分类" if field == "category" else "") for field in METADATA_FIELDS]
        with get_connection() as conn:
            cursor = conn.execute(
                """INSERT INTO documents
                   (title, source, content, file_path, category, edition, chapter, section,
                    publisher, identifier, source_url, license)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (title, source, content, file_path, *values),
            )
            conn.commit()
            doc_id = int(cursor.lastrowid)
        chunks = self.vector.index_document(doc_id, content)
        result = self.get_document(doc_id) or {"id": doc_id}
        result["indexed_chunks"] = chunks
        return result

    async def upload_document(self, file: UploadFile, source: str = "", category: str = "未分类", **metadata) -> dict:
        safe_name = Path(file.filename or "uploaded_document").name
        target = self.upload_dir / safe_name
        content_bytes = await file.read()
        target.write_bytes(content_bytes)
        text = self._extract_text(target, content_bytes)
        return self.create_document(title=safe_name, source=source, content=text, file_path=str(target),
                                    category=category, **metadata)

    def _extract_text(self, path: Path, content: bytes) -> str:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                return "\n\n".join(
                    f"[PAGE {index}]\n{page.extract_text() or ''}"
                    for index, page in enumerate(PdfReader(path).pages, 1)
                ).strip()
            except Exception as exc:
                raise ValueError(f"PDF 文本提取失败：{exc}") from exc
        if suffix == ".docx":
            try:
                with zipfile.ZipFile(path) as archive:
                    root = ElementTree.fromstring(archive.read("word/document.xml"))
                return "\n".join("".join(node.itertext()) for node in root.iter() if node.tag.endswith("}p")).strip()
            except Exception as exc:
                raise ValueError(f"DOCX 文本提取失败：{exc}") from exc
        for encoding in ("utf-8-sig", "gb18030", "utf-16"):
            try:
                text = content.decode(encoding)
                return json.dumps(json.loads(text), ensure_ascii=False, indent=2) if suffix == ".json" else text
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
        raise ValueError("不支持的文档编码或格式；支持 txt、md、csv、json、pdf、docx")

    def list_documents(self, limit: int = 50, offset: int = 0) -> list[dict]:
        with get_connection() as conn:
            rows = conn.execute(
                f"""SELECT id, title, source, content, file_path, {', '.join(METADATA_FIELDS)}, created_at
                    FROM documents ORDER BY id DESC LIMIT ? OFFSET ?""", (limit, offset)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_document(self, document_id: int) -> dict | None:
        with get_connection() as conn:
            row = conn.execute(
                f"""SELECT id, title, source, content, file_path, {', '.join(METADATA_FIELDS)}, created_at
                    FROM documents WHERE id = ?""", (document_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_document(self, document_id: int, title: str | None = None, source: str | None = None,
                        content: str | None = None, **metadata) -> dict | None:
        old = self.get_document(document_id)
        if old is None:
            return None
        values = [metadata.get(field) if metadata.get(field) is not None else old.get(field, "") for field in METADATA_FIELDS]
        new_title = title if title is not None else old["title"]
        new_source = source if source is not None else old["source"]
        new_content = content if content is not None else old["content"]
        with get_connection() as conn:
            conn.execute(
                f"""UPDATE documents SET title=?, source=?, content=?,
                    {', '.join(field + '=?' for field in METADATA_FIELDS)} WHERE id=?""",
                (new_title, new_source, new_content, *values, document_id),
            )
            conn.commit()
        self.vector.index_document(document_id, new_content)
        return self.get_document(document_id)

    def delete_document(self, document_id: int) -> bool:
        old = self.get_document(document_id)
        if old is None:
            return False
        self.vector.delete_document(document_id)
        with get_connection() as conn:
            cursor = conn.execute("DELETE FROM documents WHERE id = ?", (document_id,))
            conn.commit()
        file_path = old.get("file_path")
        if file_path:
            path = Path(file_path)
            if path.exists() and path.is_file() and self.upload_dir in path.parents:
                path.unlink()
        return cursor.rowcount > 0
