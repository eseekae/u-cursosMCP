# CLAUDE.md

Servidor MCP **de solo lectura** para que Claude lea U-Cursos (Universidad de Chile). Python, SDK `mcp` 2.x, transporte stdio. Open source (MIT). Se distribuye como extensión de Claude Desktop (`.mcpb`, runtime uv). Ver `README.md` para instalación.

Proyecto open source hecho por estudiantes de la FCFM. Responder en español chileno, directo y sin relleno.

## Reglas (no negociables)

- **Solo lectura.** Nunca agregar tools que entreguen tareas, publiquen en foros, manden correos o modifiquen nada en U-Cursos.
- **Solo cursos inscritos.** Toda tool que reciba `curso_path` pasa por `curso_inscrito()` (server.py), y las descargas por `ruta_descarga()`. No agregar acceso a secciones o semestres donde el usuario no está inscrito.
- **Nunca leer, imprimir ni commitear la sesión** (`~/.ucursos-mcp/` o el antiguo `.session/`: son las cookies de su cuenta). `settings.json` lo bloquea; no intentar rodearlo.
- **Nunca automatizar el login** ni pedirle la clave. El login es manual porque Cuenta UChile tiene reCAPTCHA: la tool `iniciar_sesion` (o `ucursos-login`) solo abre Edge/Chrome y el usuario escribe su clave ahí.
- **No commitear datos de terceros**: nombres, RUT, correos o notas de otras personas. Los fixtures se anonimizan y se revisan antes de commitear.
- Ser un cliente educado: el cliente ya espera 0,5 s entre requests. No hacer loops masivos sobre todos los cursos sin que lo pida.
- Código, comentarios y commits en español. **No usar guiones largos (em dash)** en ningún texto.

## Arquitectura

```
src/ucursos_mcp/
  auth.py     login manual con Playwright (Edge/Chrome instalado) -> ~/.ucursos-mcp/ucursos.storage_state.json
  client.py   httpx con esas cookies; decodifica ISO-8859-1; lanza SessionExpired
  parsers.py  HTML -> modelos. ÚNICA capa que conoce el HTML de U-Cursos
  documentos.py  archivo descargado -> texto (pypdf, python-docx, python-pptx). No sabe de U-Cursos
  models.py   DTOs pydantic
  server.py   tools MCP (MCPServer, patrón Facade). Errores esperables -> ToolError (decorador errores_legibles)
mcpb_server.py             entrada de la extensión (Claude Desktop corre `uv run --directory <ext> mcpb_server.py`)
manifest.json, .mcpbignore extensión .mcpb; el workflow release.yml la arma al crear un tag v*
scripts/capturar_html.py   baja una página con la sesión y la guarda anonimizada en tests/fixtures/
tests/test_parsers.py      tests sintéticos + tests sobre fixtures reales si existen
tests/test_documentos.py   extracción de texto con archivos armados en memoria
tests/test_server.py       errores legibles, cursos inscritos, rutas de descarga, paginación
```

Si U-Cursos cambia el diseño, se toca **solo `parsers.py`**.

## Comandos

```powershell
uv pip install -e ".[dev]"                     # instalar con pytest
uv run playwright install msedge               # solo si no tienes Edge ni Chrome instalado
uv run ucursos-login                           # login manual desde terminal (alternativa a la tool iniciar_sesion)
uv run pytest -q                               # tests
uv run mcp dev src/ucursos_mcp/server.py       # MCP Inspector (probar tools a mano)
uv run python scripts/capturar_html.py <ruta> <nombre>   # fixture anonimizado
npx @anthropic-ai/mcpb pack . ucursos.mcpb     # armar la extensión de Claude Desktop
```

Al subir de versión, cambiarla en `manifest.json` y `pyproject.toml` a la vez.

`.mcp.json` registra el server en Claude Code (`ucursos`), así que dentro de este proyecto Claude puede llamar las tools directamente para probarlas.

## Skills del proyecto (`.claude/skills/`)

| Skill | Cuándo usarla |
|---|---|
| `arreglar-parser` | Una tool devuelve vacío, basura o tildes rotas. Flujo: sesión, charset, capturar HTML, corregir selector, test |
| `nueva-tool` | Agregar algo nuevo que Claude pueda ver (calendario, foro, horario, asistencias) respetando las capas |
| `mcp-builder` | Oficial de Anthropic (Apache 2.0). Buenas prácticas de diseño de tools, nombres, respuestas y evaluaciones. Habla de FastMCP: aquí es `MCPServer` (ver su `VENDORED.md`) |

Skill externa opcional: `scrapling` (disponible en claude.ai) sirve si algún día hay que lidiar con bloqueos anti-bot, pero hoy no hace falta: httpx + BeautifulSoup alcanza.

## Problemas típicos

| Síntoma | Causa probable | Qué hacer |
|---|---|---|
| `SessionExpired` | Cookies vencidas | Tool `iniciar_sesion` (o `uv run ucursos-login`) |
| `Ã¡`, `Ã±` o `�` en los datos | Charset mal decodificado | Revisar `resp.encoding` en `client.get_html` (debe ser Latin-1) |
| Tool devuelve `[]` | Cambió el HTML | Skill `arreglar-parser` |
| `ModuleNotFoundError: mcp.server.fastmcp` | Código o ejemplo de la API 1.x | Usar `from mcp.server.mcpserver import MCPServer` |
| reCAPTCHA no pasa en el login | Chromium de Playwright detectado | Usar `UCURSOS_BROWSER_CHANNEL=msedge` o `chrome` (navegador real) |
| Tool devuelve solo `Error executing tool X` | Excepción que no es ToolError | Capturarla en `errores_legibles` (server.py) |
| Claude Code no ve el server | `.mcp.json` no aprobado o deps no instaladas | `/mcp` en Claude Code; correr `uv pip install -e .` |

## Hallazgos del reconocimiento (19/10/2026)

- Login: POST `/b/auth/api` devuelve `{u: <url>}` que redirige a `oauth2.uchile.cl/authorize` (OIDC, code flow, con reCAPTCHA).
- Tras loguearse, la URL contiene `/usuario/<hash32>/`.
- URLs de curso: `/{institucion}/{año}/{semestre}/{codigo}/{seccion}/{servicio}/`.
- Servicios de un curso: historial, material_docente, asistencias2, calendario, clases, correo, encuestas, enlaces, foro, integrantes, material_alumnos, notas, novedades, datos_curso, tareas. Objetos individuales: `{servicio}/o/{id}`.
- Vistas del usuario: `/usuario/<hash>/{mis_canales, todos_cursos, horario, tareas_usuario, favoritos}/`.
- Tablas: tareas_usuario -> `table.sortable` (N°, Tarea, Fecha Límite, Estado). material_docente -> `table#materiales` (Descargar, N°, Título, Por), descarga vía link con `bajar`. notas -> tabla con th "Evaluación". novedades -> `div.post.objeto`.
- Hay requests AJAX (`?accion=...&_ajax=...` con token csrf). Posible mejora: usar esos endpoints si devuelven JSON.
- Respuestas en ISO-8859-1.

## Pendiente

1. Validar los `TODO` de `parsers.py` (tareas y novedades) con fixtures reales: skill `arreglar-parser`.
2. Tools nuevas: calendario, foro (lectura), horario: skill `nueva-tool`.
3. Detectar expiración de sesión también por redirección a la portada.
4. Evaluaciones de calidad de las tools con `mcp-builder/reference/evaluation.md`.
