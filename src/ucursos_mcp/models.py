"""Modelos de datos (DTOs) que las tools devuelven a Claude."""

from __future__ import annotations

from pydantic import BaseModel


class Curso(BaseModel):
    nombre: str
    codigo: str          # ej: CC1002
    seccion: str         # ej: 7
    institucion: str     # ej: ingenieria, bachillerato
    anio: int
    semestre: int
    path: str            # ej: ingenieria/2026/2/CC1002/7  (clave para el resto de tools)


class Tarea(BaseModel):
    titulo: str
    curso: str
    fecha_limite: str    # texto tal cual lo muestra U-Cursos ("06/11/2026 23:59")
    estado: str          # "En Plazo", "Entregada", etc.


class Material(BaseModel):
    numero: str
    titulo: str
    autor: str
    fecha: str
    descarga: str | None  # ruta relativa al curso para descargar


class Novedad(BaseModel):
    titulo: str
    autor: str
    fecha: str
    resumen: str


class TablaNotas(BaseModel):
    """Las notas varían mucho entre cursos, así que se devuelven como tabla genérica."""
    columnas: list[str]
    filas: list[list[str]]
