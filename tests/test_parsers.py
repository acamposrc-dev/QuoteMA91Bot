import io

import pytest
from openpyxl import Workbook

from app.services.parsing.base import UnrecognizedFormat
from app.services.parsing.template_csv import TemplateCsvParser
from app.services.parsing.template_xlsx import TemplateXlsxParser


def _xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_xlsx_template_ok():
    content = _xlsx([
        ["item", "descripcion", "cantidad", "marca_preferida", "specs"],
        ["Taladro percutor", "Taladro 750W mandril 13mm", 2, "Bosch", "potencia: 750W; mandril: 13mm"],
        ["Cable THW 12", "Rollo 100m", 5, None, "calibre: 12 AWG"],
    ])
    result = TemplateXlsxParser().parse("cotizacion.xlsx", content)
    assert result.method == "TEMPLATE_XLSX"
    assert len(result.items) == 2
    assert result.items[0].quantity == 2
    assert result.items[0].specs["potencia"] == "750W"
    assert result.items[1].preferred_brand is None


def test_xlsx_wrong_headers_raises():
    content = _xlsx([["producto", "qty"], ["algo", 1]])
    with pytest.raises(UnrecognizedFormat):
        TemplateXlsxParser().parse("otro.xlsx", content)


def test_csv_template_ok():
    csv_bytes = (
        "item,descripcion,cantidad,marca_preferida,specs\n"
        "Bomba de agua,Bomba centrifuga 1HP,1,,potencia: 1HP; voltaje: 110V\n"
    ).encode()
    result = TemplateCsvParser().parse("cotizacion.csv", csv_bytes)
    assert result.items[0].name == "Bomba de agua"
    assert result.items[0].specs["voltaje"] == "110V"


def test_csv_semicolon_delimiter():
    csv_bytes = (
        "item;descripcion;cantidad\n"
        "Compresor;Compresor 50L;1\n"
    ).encode()
    result = TemplateCsvParser().parse("cotizacion.csv", csv_bytes)
    assert result.items[0].name == "Compresor"
