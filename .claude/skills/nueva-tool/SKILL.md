---
name: nueva-tool
description: Agrega una tool nueva de solo lectura al MCP de U-Cursos (calendario, foro, horario, asistencias, etc.) siguiendo la arquitectura en capas del proyecto. Usar cuando el usuario quiera que Claude pueda ver algo más de U-Cursos.
---

# Agregar una tool al MCP de U-Cursos

Leer también la skill `mcp-builder` (sección de diseño de tools y `reference/mcp_best_practices.md`) para nombres, descripciones y formato de respuesta.

## 0. Chequeo de alcance

- **Solo lectura.** Si la tool entregaría una tarea, publicaría en un foro, mandaría un correo o cambiaría algo, NO se agrega. Decírselo al usuario.
- Revisar que el servicio exista en la lista de "Hallazgos" de `CLAUDE.md` (ej. `calendario`, `foro`, `asistencias2`, `horario`).

## 1. Ver el HTML real

```powershell
uv run python scripts/capturar_html.py <ruta_del_servicio> <nombre>
```

Mirar el fixture y decidir qué campos le sirven a Claude. Menos es más: solo lo que responde preguntas reales ("¿qué tengo esta semana?", "¿qué dijo el profe en el foro?").

Si la vista carga datos por AJAX (`?accion=...&_ajax=...`), revisar si ese endpoint devuelve JSON: sería más estable que parsear HTML.

## 2. Implementar por capas (en este orden)

1. **`models.py`**: un modelo pydantic con los campos elegidos. Fechas como texto tal cual las muestra U-Cursos, salvo que se necesite comparar.
2. **`parsers.py`**: `parse_<servicio>(html) -> list[Modelo]`. Devolver `[]` si no encuentra la estructura; nunca explotar.
3. **`client.py`**: solo si la ruta no se arma con `servicio_curso(curso_path, servicio)` o con `/usuario/{user_id}/...`.
4. **`server.py`**: la tool con `@mcp.tool()`.
   - Docstring en español, una línea clara: Claude decide cuándo usarla leyendo eso.
   - Parámetros simples (`curso_path: str`, `limite: int = 10`).
   - Devolver `list[dict]` con `model_dump()`.
   - Límite por defecto para listas largas (foros, historial).

## 3. Tests

- Test sintético en `tests/test_parsers.py`.
- Agregar el fixture al diccionario `REALES` para que `test_fixture_real` lo cubra.
- `uv run pytest -q`

## 4. Probar de punta a punta

```powershell
uv run mcp dev src/ucursos_mcp/server.py
```

O en Claude Code, con `.mcp.json` ya configurado: pedirle a Claude que use la tool nueva.

## 5. Documentar

- Fila nueva en la tabla de tools de `README.md`.
- Sacar el ítem de "Pendiente" en `CLAUDE.md` si estaba ahí.
- Commit con mensaje en español: `Agrega tool <nombre>`.
