"""Split source documents into chunks with metadata.

Each document type gets a structure-aware splitter rather than fixed-size windows, so that a retrieved
passage corresponds to a meaningful unit (one objective definition, one docstring section, one paper
section) and can be cited precisely.
"""

import ast
import re
from dataclasses import asdict, dataclass

from ingestion.document_loader import SourceDocument

MAX_CHARS = 1800


@dataclass
class Chunk:
    chunk_id: str
    content: str
    problem_id: str  # e.g. RE21, or RE_SUITE / GENERAL
    objective_id: str  # f1, f2, ... or "all"
    component_type: str
    source_file: str
    source_section: str
    source_location: str
    document_type: str

    def metadata(self) -> dict:
        d = asdict(self)
        d.pop("content")
        return d


# ---------------------------------------------------------------- python source


def _call_name(node: ast.stmt) -> str | None:
    value = getattr(node, "value", None)
    if isinstance(value, ast.Call):
        f = value.func
        return f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
    return None


def _kwarg(node: ast.stmt, key: str) -> str | None:
    for kw in node.value.keywords:  # type: ignore[attr-defined]
        if kw.arg == key and isinstance(kw.value, ast.Constant):
            return str(kw.value.value)
    return None


_DOC_SECTIONS = {"References:": "docstring_references", "Args:": "docstring_parameters", "Returns:": "docstring_returns"}


def _split_docstring(doc: str) -> list[tuple[str, str]]:
    """Return (component_type, text) parts: formulation body, then References/Args/Returns sections."""
    parts, current, label = [], [], "docstring_formulation"
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped in _DOC_SECTIONS:
            if "".join(current).strip():
                parts.append((label, "\n".join(current).strip()))
            current, label = [stripped], _DOC_SECTIONS[stripped]
        else:
            current.append(line)
    if "".join(current).strip():
        parts.append((label, "\n".join(current).strip()))
    return parts


def chunk_python_source(doc: SourceDocument, function_prefix: str = "re") -> list[Chunk]:
    tree = ast.parse(doc.text)
    chunks: list[Chunk] = []
    for fn in tree.body:
        if not (isinstance(fn, ast.FunctionDef) and re.fullmatch(rf"{function_prefix}\d+", fn.name)):
            continue
        pid = fn.name.upper()
        header = f"[{pid} | {doc.file} | function {fn.name}]\n"
        signature = ast.get_source_segment(doc.text, fn).split(":\n", 1)[0] + ":"

        docstring = ast.get_docstring(fn) or ""
        for ctype, text in _split_docstring(docstring):
            if ctype == "docstring_returns":  # "Returns: Problem: an instance of ..." carries no information
                continue
            body = f"{signature}\n{text}" if ctype in ("docstring_formulation", "docstring_parameters") else text
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.file}::{fn.name}::{ctype}",
                    content=header + body,
                    problem_id=pid,
                    objective_id="all",
                    component_type=ctype,
                    source_file=doc.file,
                    source_section=f"{fn.name} docstring ({ctype.removeprefix('docstring_')})",
                    source_location=f"lines {fn.body[0].lineno}-{fn.body[0].end_lineno}",
                    document_type=doc.document_type,
                )
            )

        # Group the function body: consecutive statements of the same kind form one chunk, except that
        # every Objective/Constraint gets its own chunk so it can carry an objective id.
        groups: list[tuple[str, list[ast.stmt]]] = []
        for stmt in fn.body[1:] if docstring else fn.body:
            kind = {
                "Variable": "decision_variables",
                "Objective": "objective_definition",
                "Constraint": "constraint_definition",
                "ExtraFunction": "extra_function",
                "Problem": "problem_assembly",
            }.get(_call_name(stmt) or "", "problem_assembly" if isinstance(stmt, ast.Return) else "parameter_setup")
            if kind in ("objective_definition", "constraint_definition") or not groups or groups[-1][0] != kind:
                groups.append((kind, [stmt]))
            else:
                groups[-1][1].append(stmt)

        for i, (kind, stmts) in enumerate(groups):
            text = "\n".join(ast.get_source_segment(doc.text, s) for s in stmts)
            obj_id = "all"
            if kind == "objective_definition":
                sym = _kwarg(stmts[0], "symbol") or ""
                obj_id = sym.replace("_", "") if re.fullmatch(r"f_\d+", sym) else sym or "all"
            for j, piece in enumerate(_split_long(text)):
                chunks.append(
                    Chunk(
                        chunk_id=f"{doc.file}::{fn.name}::{kind}::{i}" + (f".{j}" if j else ""),
                        content=f"{header}{signature}\n    ...\n{piece}",
                        problem_id=pid,
                        objective_id=obj_id,
                        component_type=kind,
                        source_file=doc.file,
                        source_section=f"{fn.name} body ({kind})",
                        source_location=f"lines {stmts[0].lineno}-{stmts[-1].end_lineno}",
                        document_type=doc.document_type,
                    )
                )
    return chunks


# ---------------------------------------------------------------- markdown documentation


def _problem_scope(text: str) -> str:
    found = {m.upper() for m in re.findall(r"\bre\d{2}\b", text, flags=re.IGNORECASE)}
    if len(found) == 1:
        return found.pop()
    return "RE_SUITE" if found else "GENERAL"


def _split_long(text: str) -> list[str]:
    if len(text) <= MAX_CHARS:
        return [text]
    out, buf = [], ""
    for para in re.split(r"\n\s*\n", text):
        if buf and len(buf) + len(para) > MAX_CHARS:
            out.append(buf.strip())
            buf = ""
        buf += para + "\n\n"
    if buf.strip():
        out.append(buf.strip())
    return out


def chunk_markdown(doc: SourceDocument) -> list[Chunk]:
    chunks: list[Chunk] = []
    sections = re.split(r"(?m)^(?=#{1,3} )", doc.text)
    for i, section in enumerate(s for s in sections if s.strip()):
        title = section.splitlines()[0].lstrip("# ").strip()
        for j, piece in enumerate(_split_long(section.strip())):
            chunks.append(
                Chunk(
                    chunk_id=f"{doc.file}::{i}.{j}",
                    content=f"[{doc.file} | {title}]\n{piece}",
                    problem_id=_problem_scope(piece),
                    objective_id="all",
                    component_type="documentation",
                    source_file=doc.file,
                    source_section=title,
                    source_location=f"section {i}, part {j}",
                    document_type=doc.document_type,
                )
            )
    return chunks


# ---------------------------------------------------------------- literature (Tanabe supplementary)


def chunk_literature(doc: SourceDocument) -> list[Chunk]:
    chunks: list[Chunk] = []
    for section in re.split(r"(?m)^(?=S\.\d+\.\d+\. )", doc.text):
        if not section.strip():
            continue
        title = section.splitlines()[0].strip()
        m = re.search(r"RE(\d)-\d+-(\d)", title)  # RE2-4-1 -> RE21
        pid = f"RE{m.group(1)}{m.group(2)}" if m else "RE_SUITE"
        chunks.append(
            Chunk(
                chunk_id=f"{doc.file}::{title.split()[0]}",
                content=f"[{pid} | Tanabe & Ishibuchi supplementary | {title}]\n{section.strip()}",
                problem_id=pid,
                objective_id="all",
                component_type="literature_problem_definition",
                source_file=doc.file,
                source_section=title,
                source_location=f"section {title.split()[0]}",
                document_type=doc.document_type,
            )
        )
    return chunks


def chunk_document(doc: SourceDocument) -> list[Chunk]:
    if doc.file.endswith(".py"):
        return chunk_python_source(doc)
    if doc.document_type == "literature":
        return chunk_literature(doc)
    return chunk_markdown(doc)
