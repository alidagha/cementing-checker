"""C01 structural claims only. No engineering validation, rendering or correction."""
import argparse
from collections import Counter
from io import BytesIO
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile

from docx import Document
from docx.oxml.ns import qn
from lxml.etree import XMLSyntaxError

ROOT = Path(__file__).resolve().parent
FLUIDS = ("Diesel", "Pre Flush", "Spacer", "Spacer Ahead", "Scavenger", "Main",
          "Lead", "Lead #1", "Lead #2", "Tail", "Spacer Behind", "Displacement Fluid")
SECTIONS = {
    "executive summary": "summary", "well data summary": "hardware",
    "geothermal temperature profile": "geothermal", "fluids sequence": "fluids",
    "cementing program": "cement", "pre-flush program": "preflush",
    "laboratory report": "lab", "cementing procedure": "procedure",
    "operational procedure": "procedure",
    "document control": "excluded", "directional well survey data": "excluded",
    "centralizer placement recommendation": "excluded", "attachments": "excluded",
    "contents": "excluded", "pore/frac pressure": "excluded", "iod": "excluded",
}
NUMERIC_LABEL = re.compile(r"^(volume|weight|slurry weight|density|yield|solution|bhst|bhct|bhsp|mix fluid|base fluid|solution density)(?:\s*\([^)]*\))?$", re.I)
SCALAR = re.compile(r"([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([A-Za-z°][A-Za-z0-9°/^ .()-]*)?")


class ExtractionError(ValueError):
    """Input is outside the supported, lossless structural subset."""


def norm(text):
    return " ".join(text.split()).casefold()


def heading(text):
    return SECTIONS.get(re.sub(r"^[IVX]+\.\s*", "", norm(text), flags=re.I))


def text_of(element):
    # itertext duplicates python-docx run text; read the actual Word text nodes.
    return "".join(n.text or "" if n.tag == qn("w:t") else
                   "\t" if n.tag == qn("w:tab") else "\n"
                   for n in element.iter()
                   if n.tag in (qn("w:t"), qn("w:tab"), qn("w:br"), qn("w:cr")))


def identity(text):
    """Only full printed fluid/result/table anchors establish an identity."""
    found = []
    for fluid in FLUIDS:
        if re.fullmatch(re.escape(fluid) + r"(?: Cement Slurry (?:Data|Blend Data|Additives Data|Results)| Results| Additives Data| Lab Results| Rheology)?", text.strip(), re.I):
            found.append(fluid)
    return found


def state_of(raw, numeric=False):
    stripped = raw.strip()
    if not stripped:
        return "MISSING", None, None
    if stripped in ("-", "–", "—"):
        return "DASH", None, None
    if norm(stripped) in ("n/a", "not applicable", "not applicable."):
        return "NA_PRINTED", None, None
    match = SCALAR.fullmatch(stripped)
    if match:
        # Decimal spelling retained; downstream modules decide numeric semantics.
        number, unit = match.groups()
        return ("ZERO" if float(number) == 0 else "NUMBER"), number, unit
    return ("MALFORMED" if numeric else "TEXT"), None, None


def safe_input(path):
    supplied = Path(path)
    if supplied.suffix.lower() != ".docx":
        raise ExtractionError("DOCX input required")
    resolved = supplied.resolve(strict=True)
    if not resolved.is_relative_to(ROOT) or not resolved.is_file():
        raise ExtractionError("Input escapes Checker scratch")
    # Never extract ZIP members to disk. Bound the package before handing it to docx.
    if resolved.stat().st_size > 32 * 1024 * 1024:
        raise ExtractionError("DOCX exceeds 32 MiB input limit")
    data = resolved.read_bytes()
    with zipfile.ZipFile(BytesIO(data)) as package:
        infos = package.infolist()
        if len(infos) > 2048 or sum(i.file_size for i in infos) > 64 * 1024 * 1024:
            raise ExtractionError("DOCX expansion limit")
        names = [i.filename for i in infos]
        if len(set(names)) != len(names):
            raise ExtractionError("Duplicate ZIP parts")
        for item in infos:
            name = PurePosixPath(item.filename)
            if name.is_absolute() or ".." in name.parts or "\\" in item.filename or stat.S_ISLNK(item.external_attr >> 16):
                raise ExtractionError("Unsafe ZIP member")
            if item.flag_bits & 1 or "vbaProject" in item.filename or "/embeddings/" in item.filename:
                raise ExtractionError("Encrypted/active embedded content unsupported")
            if item.filename.endswith((".xml", ".rels")):
                xml = package.read(item)
                if b"<!DOCTYPE" in xml.upper() or b"<!ENTITY" in xml.upper():
                    raise ExtractionError("DTD/entity declarations unsupported")
                if item.filename.endswith(".rels") and re.search(br'TargetMode\s*=\s*[\x22\x27]External', xml, re.I):
                    raise ExtractionError("External relationships unsupported")
        if "word/document.xml" not in names:
            raise ExtractionError("Missing Word main document")
    return data


def parse_docx(path):
    """Return deterministic JSON-compatible records; never write or access network."""
    digest = None
    try:
        data = safe_input(path)
        digest = hashlib.sha256(data).hexdigest()
        document = Document(BytesIO(data))
        body = document.element.body
        unsupported = ("altChunk", "ins", "del", "sym", "object")
        for tag in unsupported:
            if next(body.iter(qn("w:" + tag)), None) is not None:
                raise ExtractionError("Unsupported body structure: " + tag)
        if any(block.tag not in (qn("w:p"), qn("w:tbl"), qn("w:sdt"), qn("w:sectPr")) for block in body):
            raise ExtractionError("Unsupported top-level Word structure")
        records = []
        excluded_wrappers = []
        section, nearest, group = "excluded", None, []
        stage = None
        counters = Counter()
        table_number = 0

        def exclude_wrapper(node, bi, reason):
            excluded_wrappers.append({"body_block": bi, "xml_path": body.getroottree().getpath(node),
                                      "reason": reason})

        def excluded_toc(node):
            gallery = node.find("./" + qn("w:sdtPr") + "/" + qn("w:docPartObj") + "/" + qn("w:docPartGallery"))
            content = node.find(qn("w:sdtContent"))
            if gallery is None or gallery.get(qn("w:val")) != "Table of Contents" or content is None:
                return False
            if any(c.tag != qn("w:p") for c in content) or len(list(node.iter(qn("w:sdt")))) != 1 or next(node.iter(qn("w:txbxContent")), None) is not None:
                return False
            if not any(re.match(r"\s*TOC\s+", n.text or "") for n in node.iter(qn("w:instrText"))):
                return False
            for p in content:
                style = p.find("./" + qn("w:pPr") + "/" + qn("w:pStyle"))
                name = style.get(qn("w:val"), "") if style is not None else ""
                if text_of(p).strip() and not (re.fullmatch(r"TOC\d+", name) or (name == "TOCHeading" and norm(text_of(p)) == "contents")):
                    return False
            return True

        def check_wrappers(block, bi):
            for node in block.iter():
                if node.tag == qn("w:sdt"):
                    raise ExtractionError("Unsupported in-scope/unproven content control")
                if node.tag != qn("w:txbxContent"):
                    continue
                cover = (section == "excluded" and nearest is None and block.tag == qn("w:tbl")
                         and norm(text_of(node)) == "cementing program"
                         and "client:" in norm(text_of(block)) and "type of job:" in norm(text_of(block)))
                control = (section == "excluded" and nearest is not None
                           and re.sub(r"^[ivx]+\.\s*", "", norm(nearest)) == "document control"
                           and not text_of(node).strip())
                if not (cover or control):
                    raise ExtractionError("Unsupported in-scope/unproven textbox")
                exclude_wrapper(node, bi, "cover title" if cover else "empty Document Control textbox")

        def emit(raw, locator, label=None, column=None, association=None, anchor=None):
            if section == "excluded":
                return
            # Explicit excluded row/paragraph anchors; no numerical content is assessed.
            low = norm(raw)
            note_body = re.sub(r"^note\s+\d+\s*:\s*", "", low)
            if note_body == "the pore and frac pressure is based on mud weight density.":
                return
            if re.match(r"^(contents\b|iod\b|pore[/ /-]*frac\b|centralizer\b|well schematic:|temperature profile chart:|pressure and fluid sequence charts:|pumping simulation charts:)", low):
                return
            value_state, scalar, unit = state_of(raw, bool(label and raw != label and NUMERIC_LABEL.fullmatch(label.strip())))
            assoc = group if association is None else association
            counters[section] += 1
            step = re.match(r"\s*(\d+)[.)]\s", raw) if section == "procedure" else None
            note = re.match(r"\s*NOTE\s+(\d+)\s*:", raw, re.I)
            records.append({"source_order": len(records), "section": section,
                "ordinal_inside_section": counters[section], "heading": nearest,
                "locator": locator, "table_anchor": anchor,
                "printed_label": label, "column_label": column, "raw_text": raw,
                "value_state": value_state, "parsed_scalar": scalar, "unit": unit,
                "association": assoc[0] if len(assoc) == 1 else None,
                "association_state": "EXPLICIT" if len(assoc) == 1 else "AMBIGUOUS" if len(assoc) > 1 else "NOT_VERIFIABLE",
                "association_candidates": assoc, "step": int(step[1]) if step else None,
                "stage": stage,
                "note": int(note[1]) if note else None,
                "verification_status": "NOT_VERIFIABLE", "source_document_sha256": digest})

        def walk_table(table, block, path, inherited):
            nonlocal table_number
            table_number += 1
            tn = table_number
            rows = table.findall(qn("w:tr"))
            first = [text_of(c) for c in rows[0].findall(qn("w:tc"))] if rows else []
            anchor = " | ".join(dict.fromkeys(t for t in first if t.strip()))
            explicit = list(dict.fromkeys(f for t in first for f in identity(t)))
            assoc = explicit or inherited
            # A table anchor cannot silently override a contradictory printed lab heading.
            if explicit and inherited and explicit != inherited and section == "lab":
                assoc = list(dict.fromkeys(inherited + explicit))
            headers = []
            for ri, row in enumerate(rows):
                cells = row.findall(qn("w:tc"))
                cell_texts = [text_of(c) for c in cells]
                if cell_texts and norm(cell_texts[0]).startswith(("iod", "pore/frac", "centralizer placement")):
                    continue
                if cell_texts and norm(cell_texts[0]) in ("item", "material type", "rpm", "type", "md (m)", "description"):
                    headers = cell_texts
                row_assoc = identity(cell_texts[0]) if section == "fluids" and cell_texts else []
                col = 0
                for ci, cell in enumerate(cells):
                    span = cell.find("./" + qn("w:tcPr") + "/" + qn("w:gridSpan"))
                    width = int(span.get(qn("w:val"))) if span is not None else 1
                    left = cell_texts[ci - 1] if ci else ""
                    label = left if NUMERIC_LABEL.fullmatch(left.strip()) else (cell_texts[0] if cell_texts else None)
                    column_label = headers[ci] if ci < len(headers) else None
                    if column_label and norm(column_label).startswith("iod"):
                        col += width
                        continue
                    for pi, child in enumerate(cell):
                        loc = {"body_block": block, "table": tn, "table_path": path, "row": ri, "column": col, "column_span": width, "paragraph": pi}
                        if child.tag == qn("w:p"):
                            emit(text_of(child), loc, label, column_label, row_assoc or assoc, anchor)
                        elif child.tag == qn("w:tbl"):
                            walk_table(child, block, path + [ri, col], assoc)
                    col += width

        for bi, block in enumerate(body):
            if block.tag == qn("w:sdt"):
                if not excluded_toc(block):
                    raise ExtractionError("Unsupported in-scope/unproven content control")
                exclude_wrapper(block, bi, "TOC gallery, field and paragraph styles")
                continue
            if block.tag == qn("w:p"):
                raw = text_of(block)
                new_section = heading(raw)
                if new_section is not None:
                    section, nearest, group = new_section, raw, []
                    stage = None
                elif raw.strip() and not identity(raw) and (style := block.find("./" + qn("w:pPr") + "/" + qn("w:pStyle"))) is not None and style.get(qn("w:val"), "").lower().startswith("heading"):
                    # Unknown headings break inherited identity, never invent applicability.
                    group = []
                    nearest = raw
                    section = "unknown"
                    stage = None
                explicit = identity(raw)
                if explicit:
                    group = explicit
                    stage = None
                stage_match = re.fullmatch(r"\s*Stage\s+(\d+)\s*:?\s*", raw, re.I)
                if stage_match:
                    stage = int(stage_match[1])
                check_wrappers(block, bi)
                emit(raw, {"body_block": bi, "paragraph": bi, "table": None}, anchor=None)
            elif block.tag == qn("w:tbl"):
                check_wrappers(block, bi)
                if section != "excluded":
                    walk_table(block, bi, [], group)
        return {"schema_version": "c01.1", "status": "EXTRACTED_UNVERIFIED",
                "source_document_sha256": digest, "records": records, "excluded_wrappers": excluded_wrappers,
                "summary": {"records": len(records), "sections": dict(counters),
                            "value_states": dict(Counter(r["value_state"] for r in records))}}
    except (ExtractionError, OSError, ValueError, KeyError, XMLSyntaxError, zipfile.BadZipFile) as error:
        return {"schema_version": "c01.1", "status": "REJECTED", "source_document_sha256": digest,
                "records": [], "error": str(error)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("docx")
    args = parser.parse_args()
    result = parse_docx(args.docx)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 2 if result["status"] == "REJECTED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
