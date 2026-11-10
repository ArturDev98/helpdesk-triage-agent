"""Quita datos personales antes de que el texto salga hacia el modelo, el chat o la base.
Los nombres propios en texto libre no se detectan: el solicitante se descarta en la fuente."""
import re

_RULES = [
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[correo]"),
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "[tarjeta]"),
    # Antes que el teléfono: una cédula de 10 dígitos con su etiqueta es documento, no celular.
    # Con puntos de miles solo si lo antecede la etiqueta: "1.250.000" sin etiqueta es un monto.
    (re.compile(r"(?i)\b(cc|c\.c\.|cédula|cedula|documento|nit|dni|ce)(\s*[:#]?\s*)\d[\d.\-]{5,14}\d"),
     r"\1\2[documento]"),
    (re.compile(r"(?<!\d)(?:\+?\d{1,3}[ -]?)?(?:\(?\d{3}\)?[ -]?)\d{3}[ -]?\d{4}(?!\d)"), "[teléfono]"),
    (re.compile(r"(?<![\d.])\d{8,12}(?![\d.])"), "[documento]"),
]


def redact(text):
    text = text or ""
    for pattern, label in _RULES:
        text = pattern.sub(label, text)
    return text
