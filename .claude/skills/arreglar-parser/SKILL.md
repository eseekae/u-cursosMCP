---
name: arreglar-parser
description: Diagnostica y arregla una tool del MCP de U-Cursos que devuelve vacío, datos raros o caracteres rotos, normalmente porque U-Cursos cambió su HTML. Usar cuando el usuario diga que una tool no trae nada, trae basura, o "se rompió".
---

# Arreglar un parser de U-Cursos

El 90% de las fallas son una de tres: sesión expirada, charset mal decodificado, o U-Cursos cambió el HTML. Descartarlas en ese orden.

## 1. Descartar sesión expirada

- Si el error dice `SessionExpired`, no hay nada que arreglar en código: pedirle al usuario que corra `uv run ucursos-login`.
- Nunca leer `.session/` para "revisar" las cookies.

## 2. Descartar charset

- Si salen `Ã¡`, `Ã±` o `�` en vez de tildes, el problema está en `client.get_html`. U-Cursos manda ISO-8859-1; verificar que `resp.encoding` termine siendo Latin-1.

## 3. Capturar el HTML real

```powershell
uv run python scripts/capturar_html.py <ruta> <nombre>
```

Rutas típicas (el `me` se reemplaza solo por el hash del usuario):

| Tool | Ruta | Nombre de fixture |
|---|---|---|
| listar_cursos | `/usuario/me/mis_canales/` | `home` |
| tareas (respaldo) | `/usuario/me/tareas_usuario/` | `tareas_usuario` |
| tareas | `<curso_path>/tareas/` | `tareas` |
| detalle_tarea | la `url` que devuelve tareas | `detalle_tarea` |
| notas | `<curso_path>/notas/` | `notas` |
| material_docente | `<curso_path>/material_docente/` | `material_docente` |
| novedades | `<curso_path>/novedades/` | `novedades` |

El script anonimiza, pero **revisar el archivo** antes de commitearlo: buscar RUT, correos, nombres y notas de otras personas. Si hay datos de terceros que no se pudieron limpiar, no commitear el fixture (agregarlo a `.gitignore`).

## 4. Corregir el selector

- Abrir el fixture, ubicar el bloque que corresponde y comparar con el selector en `src/ucursos_mcp/parsers.py`.
- Cambiar **solo** `parsers.py`. `client.py` y `server.py` no saben de HTML.
- Preferir selectores por `id` o clase estable por sobre posiciones (`tds[2]`). Si hay que usar posición, mapear las columnas leyendo los `<th>`.
- Si el campo puede faltar, devolver `""` en vez de explotar.

## 5. Verificar

```powershell
uv run pytest -q
```

`test_fixture_real` usa automáticamente `tests/fixtures/<nombre>.html` (local, ignorado por git) y `tests/fixtures/esqueletos/<nombre>.html` (el que se commitea). Si el arreglo cubre un caso nuevo, agregar un test sintético en `tests/test_parsers.py`.

Probar la tool de punta a punta con el MCP Inspector: `uv run mcp dev src/ucursos_mcp/server.py`.

## 6. Registrar

Si cambió la estructura de una vista, actualizar la sección "Hallazgos" de `CLAUDE.md` con la fecha.
