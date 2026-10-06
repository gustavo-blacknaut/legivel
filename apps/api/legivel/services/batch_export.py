import csv
import io
import json
import zipfile

from openpyxl import Workbook

from legivel.services.documents import document_values


def safe_cell(value):
    text = str(value or "")
    return "'" + text if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) else text


def export_batch(items: list, entity: str, format: str, store) -> bytes:
    entries = [
        {
            "id": item.id,
            "tipo": item.doc_type if entity == "document" else item.module,
            "status": item.status,
            **(document_values(item) if entity == "document" else item.data.get("fields", {})),
        }
        for item in items
    ]
    columns = list(dict.fromkeys(key for entry in entries for key in entry))
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.DictWriter(output, fieldnames=columns, delimiter=";")
        writer.writeheader()
        writer.writerows({name: safe_cell(entry.get(name)) for name in columns} for entry in entries)
        return ("\ufeff" + output.getvalue()).encode("utf-8")
    if format == "xlsx":
        workbook = Workbook(write_only=True)
        sheet = workbook.create_sheet("Documentos" if entity == "document" else "Leituras")
        sheet.append(columns)
        for entry in entries:
            sheet.append([safe_cell(entry.get(name)) for name in columns])
        output = io.BytesIO()
        workbook.save(output)
        return output.getvalue()
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("dados.json", json.dumps(entries, ensure_ascii=False, indent=2))
        for item in items:
            pages = item.images if entity == "document" else item.pages
            for index, page in enumerate(pages, 1):
                if entity == "document" and page.kind != "page":
                    continue
                if page.original_path:
                    extension = {"image/png": "png", "image/webp": "webp", "image/heif": "heic"}.get(page.original_mime, "jpg")
                    archive.writestr(f"{entity}-{item.id}/pagina-{index}.{extension}", store.load(page.original_path))
    return output.getvalue()
