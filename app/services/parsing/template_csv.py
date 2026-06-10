"""Parser deterministico de la plantilla en CSV (mismas columnas que la Excel)."""

import csv
import io

from app.models import ParseMethod
from app.services.parsing.base import DocumentParser, ParsedItem, ParseResult, UnrecognizedFormat
from app.services.parsing.template_xlsx import REQUIRED, parse_specs


class TemplateCsvParser(DocumentParser):
    method = ParseMethod.TEMPLATE_CSV.value

    def can_handle(self, filename: str, content: bytes) -> bool:
        return filename.lower().endswith((".csv", ".tsv"))

    def parse(self, filename: str, content: bytes) -> ParseResult:
        try:
            textio = io.StringIO(content.decode("utf-8-sig"))
        except UnicodeDecodeError:
            textio = io.StringIO(content.decode("latin-1"))

        sample = textio.read(4096)
        textio.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel

        reader = csv.DictReader(textio, dialect=dialect)
        if reader.fieldnames is None:
            raise UnrecognizedFormat("CSV sin encabezados")
        fields = {f.strip().lower() for f in reader.fieldnames}
        if not REQUIRED.issubset(fields):
            raise UnrecognizedFormat(f"Encabezados no matchean: {sorted(fields)}")

        items: list[ParsedItem] = []
        for row in reader:
            row = {k.strip().lower(): (v or "").strip() for k, v in row.items() if k}
            if not row.get("item"):
                continue
            try:
                qty = max(1, int(float(row.get("cantidad") or 1)))
            except ValueError:
                raise UnrecognizedFormat(f"Cantidad invalida: {row.get('cantidad')}")
            items.append(
                ParsedItem(
                    name=row["item"],
                    description=row.get("descripcion") or None,
                    quantity=qty,
                    preferred_brand=row.get("marca_preferida") or None,
                    specs=parse_specs(row.get("specs")),
                )
            )
        if not items:
            raise UnrecognizedFormat("CSV reconocido pero sin items")
        return ParseResult(items=items, method=self.method)
