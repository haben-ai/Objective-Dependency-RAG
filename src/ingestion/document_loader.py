"""Load the raw source documents listed in data/documents/SOURCES.json."""

import json
from dataclasses import dataclass

from config import DOCUMENTS


@dataclass
class SourceDocument:
    file: str
    text: str
    document_type: str  # source_code | documentation | literature
    origin: str
    repo: str
    commit: str


def load_documents() -> list[SourceDocument]:
    manifest = json.loads((DOCUMENTS / "SOURCES.json").read_text())
    return [
        SourceDocument(
            file=m["file"],
            text=(DOCUMENTS / m["file"]).read_text(),
            document_type=m["document_type"],
            origin=m["origin"],
            repo=m["repo"],
            commit=m["commit"],
        )
        for m in manifest
    ]
