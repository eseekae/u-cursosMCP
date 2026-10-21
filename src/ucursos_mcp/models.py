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


class CursoRef(BaseModel):
    """Curso al que pertenece una tarea. `path` puede venir vacío si solo se supo el nombre."""
    nombre: str = ""
    codigo: str = ""
    path: str = ""


class Tarea(BaseModel):
    id: str | None             # se pasa a detalle_tarea
    titulo: str
    curso: CursoRef | None
    url: str | None            # ruta de la tarea en U-Cursos (/inst/año/sem/código/sección/tareas/...)
    fecha_limite: str | None   # ISO 8601 con zona de Santiago ("2026-11-06T23:59:00-03:00"), o solo fecha
    estado: str                # pendiente, entregada, atrasada, cerrada o desconocido
    fecha_entrega: str | None  # ISO 8601, si ya entregaste
    con_atraso: bool | None    # si la entrega fue fuera de plazo (None si no hay entrega)
    estado_texto: str          # texto original de U-Cursos, por si la normalización se equivoca


class Archivo(BaseModel):
    nombre: str
    descarga: str        # se pasa a leer_material o descargar_material


class DetalleTarea(BaseModel):
    id: str | None
    titulo: str
    url: str
    enunciado: str
    fecha_apertura: str | None
    fecha_cierre: str | None
    estado: str
    estado_texto: str
    fecha_entrega: str | None
    con_atraso: bool | None
    nota: str | None
    comentarios: str | None
    adjuntos: list[Archivo]     # archivos del enunciado
    entregados: list[Archivo]   # lo que entregó el usuario
    campos: dict[str, str]      # todos los pares "etiqueta: valor" de la página, tal cual


class Material(BaseModel):
    categoria: str       # carpeta de U-Cursos (Ayudantías, Pautas, ...); "" si no hay
    numero: str          # se reinicia en cada categoría
    titulo: str
    autor: str
    fecha: str
    descarga: str | None  # ruta relativa al curso para descargar


class Novedad(BaseModel):
    titulo: str
    autor: str
    fecha: str
    texto: str
    enlaces: list[str]


class TablaNotas(BaseModel):
    """Las notas varían mucho entre cursos, así que se devuelven como tabla genérica."""
    columnas: list[str]
    filas: list[list[str]]
