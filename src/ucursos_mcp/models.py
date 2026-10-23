"""Modelos de datos (DTOs) que las tools devuelven a Claude."""

from __future__ import annotations

from pydantic import BaseModel, Field


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


class Tabla(BaseModel):
    columnas: list[str]
    filas: list[list[str]]


class TablaNotas(Tabla):
    """Las notas varían mucho entre cursos, así que se devuelven como tabla genérica."""


class Enlace(BaseModel):
    texto: str
    url: str             # ruta dentro del curso (se abre con leer_seccion) o link externo


class Item(BaseModel):
    """Un objeto de una sección: tema del foro, evento del calendario, clase, enlace, ..."""
    titulo: str
    autor: str
    fecha: str | None    # ISO 8601 si se encontró una fecha
    texto: str
    url: str | None      # ruta del objeto, para abrirlo con leer_seccion(ruta=...)
    enlaces: list[str]


class MensajeForo(BaseModel):
    id: str | None
    autor: str
    rol: str | None      # cargo en el curso: profesor de catedra, profesor auxiliar, ayudante, alumno, ...
    fecha: str | None    # ISO 8601
    texto: str
    url: str | None
    nuevo: bool          # no leído por el usuario


class TemaForo(MensajeForo):
    titulo: str
    lecturas: int | None
    total_respuestas: int
    respuestas: list[MensajeForo]


class Foro(BaseModel):
    temas: list[TemaForo]
    pagina: int
    paginas: dict[str, str] = Field(default_factory=dict, exclude=True)  # "2", "siguiente" -> ruta


class Evento(BaseModel):
    """Bloque del calendario de un curso o del horario del usuario."""
    fecha: str | None    # AAAA-MM-DD
    dia: str             # lunes, martes, ...
    inicio: str | None   # ISO 8601 con hora de Chile; None si es de todo el día
    fin: str | None
    todo_el_dia: bool
    titulo: str
    tipo: str | None     # Cátedra, Auxiliar, Control, ... (la etiqueta de color)
    sala: str | None
    curso: CursoRef | None  # solo en el horario, que mezcla todos los cursos


class Calendario(BaseModel):
    semana_inicio: str | None   # AAAA-MM-DD
    semana_fin: str | None
    eventos: list[Evento]
    feriados: list[str]                 # AAAA-MM-DD, de todo el año que muestra U-Cursos
    eventos_por_dia: dict[str, int]     # AAAA-MM-DD -> cantidad, solo días con eventos
    rutas: dict[str, str] = Field(default_factory=dict, exclude=True)  # fecha, "anterior", "siguiente" -> ruta


class Contenido(BaseModel):
    """Página de cualquier sección, ordenada sin conocer su diseño (ver parsers.parse_contenido)."""
    titulo: str
    url: str
    campos: dict[str, str]   # pares "etiqueta: valor" (Profesor, Horario, ...)
    items: list[Item]
    tablas: list[Tabla]
    texto: str               # el resto del texto de la página
    archivos: list[Archivo]  # su `descarga` va a leer_material o descargar_material
    enlaces: list[Enlace]
