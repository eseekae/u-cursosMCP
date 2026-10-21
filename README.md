# ucursos-mcp

Servidor MCP **de solo lectura** para que Claude lea tu U-Cursos (Universidad de Chile): cursos, tareas, notas, novedades y el contenido del material docente (PDF, Word y PowerPoint).

No es oficial ni está afiliado a la Universidad. Es open source (MIT): úsalo, modifícalo y mejóralo.

## Instalar en Claude Desktop (sin terminal)

1. Descarga `ucursos.mcpb` desde la última versión en [Releases](https://github.com/eseekae/u-cursosMCP/releases).
2. En Claude Desktop: **Configuración → Extensiones** y arrastra el archivo (o haz doble clic sobre él).
3. Pulsa **Instalar**. La primera vez tarda un poco: Claude Desktop descarga Python y las librerías.
4. En un chat nuevo, pídele: *"Revisa mis cursos de U-Cursos"*.
5. Claude abre U-Cursos en tu navegador de siempre (o en el que le digas). Inicia sesión ahí como cualquier día y avísale cuando ya estés dentro; Claude importa tu sesión desde ese mismo navegador.

Listo. Cuando la sesión expire, Claude vuelve a abrir U-Cursos para que entres de nuevo.

Funciona con Firefox, Zen, LibreWolf, Edge, Chrome, Brave, Opera, Opera GX, Vivaldi y Chromium, incluidos varios perfiles por navegador. Si usas más de uno, dile a Claude en cuál iniciaste sesión ("estoy en Zen", "perfil Universidad de Edge").

**En Windows, Firefox y Zen son lo más confiable.** Edge, Chrome y Brave nuevos cifran sus cookies con una llave ligada a la aplicación que este programa no puede leer, y bloquean el archivo de cookies mientras están abiertos. Si falla con uno de esos, Claude te muestra qué encontró en cada navegador y perfil y qué hacer.

### Qué puedes pedirle

- "¿Qué tareas tengo pendientes esta semana?"
- "¿De qué se trata la tarea 3 de Programación? Lee el enunciado"
- "Muéstrame solo las ayudantías de Cálculo"
- "Muéstrame las últimas novedades de Cálculo"
- "¿Qué material docente hay en Física?"
- "Lee la guía 3 de Física y explícame el ejercicio 2"
- "¿Qué entra en el control 2 de Cálculo?"
- "¿Cómo voy con las notas de Álgebra?"

## Seguridad y privacidad

- **Tu clave nunca pasa por el código ni por Claude**: inicias sesión tú, en tu navegador normal. El MCP solo lee las cookies del dominio de U-Cursos desde tu navegador, igual que un gestor de contraseñas con tus propios datos. No se automatiza el navegador.
- Solo se guardan las cookies de la sesión, en tu computador (`~/.ucursos-mcp/`). No se envían a ningún servidor aparte de U-Cursos.
- Ninguna tool entrega tareas, publica ni modifica nada en U-Cursos.
- Solo lee los cursos en que estás inscrito.
- Los archivos descargados quedan en tu carpeta `Descargas/U-Cursos`.

## Tools

| Tool | Qué hace |
|---|---|
| `iniciar_sesion(navegador=None)` | Abre U-Cursos en ese navegador (o el último que funcionó, o el por defecto) para que entres |
| `estado_sesion(navegador=None, perfil=None)` | Importa la sesión de ese navegador, la valida perfil por perfil y, si falla, explica qué encontró |
| `listar_cursos()` | Cursos inscritos, con su `path` |
| `tareas(curso_path=None, solo_pendientes=True, desde=None, hasta=None, solo_semestre_actual=True)` | Tareas con curso, `id`, plazo ISO 8601 (hora de Chile) y estado normalizado (pendiente, entregada, atrasada, cerrada), ordenadas por plazo |
| `detalle_tarea(curso_path, tarea_id)` | Enunciado, apertura y cierre, estado, nota, comentarios, adjuntos y archivos entregados |
| `notas(curso_path)` | Tablas de notas del curso |
| `material_docente(curso_path, categoria=None)` | Lista de material con su categoría (Ayudantías, Pautas, Clases...) |
| `leer_material(curso_path, descarga, desde=0)` | Texto de un PDF, .docx, .pptx o archivo de texto (material o adjunto de tarea), por partes |
| `descargar_material(curso_path, descarga)` | Baja un archivo (material o adjunto de tarea) a `Descargas/U-Cursos` |
| `novedades(curso_path, limite=10)` | Últimos anuncios, con texto completo y enlaces |

Si una sección no existe o da 403 (por ejemplo en una comunidad), el error dice qué secciones sí tiene ese curso.

## Para desarrolladores

### Arquitectura

```
navegadores.py  Navegadores conocidos, sus perfiles, el navegador por defecto y cómo abrir uno
auth.py         Lee las cookies de cada perfil, las valida, guarda la sesión y arma el diagnóstico
client.py       Sesión HTTP con esas cookies, decodifica Latin-1, detecta sesión expirada
parsers.py      HTML -> modelos (única capa que conoce el HTML de U-Cursos)
documentos.py   archivo -> texto (PDF, .docx, .pptx, texto)
models.py       DTOs con pydantic
server.py       Tools MCP (MCPServer del SDK mcp 2.x, transporte stdio)
mcpb_server.py  Punto de entrada de la extensión de Claude Desktop
manifest.json   Manifest de la extensión (.mcpb, runtime uv)
```

El login de U-Cursos pasa por Cuenta UChile (OAuth2/OIDC con captcha), así que no se automatiza: el usuario inicia sesión en su propio navegador y el MCP lee esa sesión. Se reutiliza hasta que expire.

Cómo se elige la sesión: `estado_sesion` lee las cookies de `u-cursos.cl` y `uchile.cl` de cada perfil (primero el navegador pedido, el último que funcionó o el por defecto) y pide la portada de U-Cursos con ellas. Una sesión vale si U-Cursos redirige a `/usuario/<hash>/` o la portada trae ese link; no se depende del nombre de ninguna cookie. Se guarda el primer perfil que funcione, junto con el navegador de origen para la próxima vez. Firefox, Zen y LibreWolf se leen directamente con SQLite (copiando también `cookies.sqlite-wal`, donde quedan las cookies recién creadas); los Chromium, con browser_cookie3. El diagnóstico de la última falla queda en `~/.ucursos-mcp/login.log` (solo nombres de cookies, nunca valores).

### Correr desde el código

```powershell
git clone https://github.com/eseekae/u-cursosMCP.git
cd u-cursosMCP
uv venv
uv pip install -e ".[dev]"
uv run pytest -q                              # tests
uv run ucursos-login --navegador zen          # abre U-Cursos y, tras entrar, importa la sesión (opcional; --perfil también)
uv run mcp dev src/ucursos_mcp/server.py      # MCP Inspector
```

**Claude Code:** abre Claude Code dentro de la carpeta del repo; `.mcp.json` ya registra el server `ucursos`.

**Fixtures:** `uv run python scripts/capturar_html.py <ruta> <nombre>` guarda una página anonimizada en `tests/fixtures/`. Revísala antes de commitear: no deben quedar nombres, RUT ni correos.

### Armar la extensión

```bash
npx @anthropic-ai/mcpb pack . ucursos.mcpb
```

El workflow `.github/workflows/release.yml` la arma y la adjunta sola al crear un tag `v*`.

### Variables de entorno

| Variable | Default |
|---|---|
| `UCURSOS_DATA` | `~/.ucursos-mcp` |
| `UCURSOS_SESSION` | `~/.ucursos-mcp/ucursos.storage_state.json` |
| `UCURSOS_BROWSER` | fuerza un navegador para abrir y leer la sesión: `edge`, `chrome`, `brave`, `vivaldi`, `opera`, `opera_gx`, `chromium`, `firefox`, `zen`, `librewolf` (por defecto: el último que funcionó, luego el por defecto, luego todos) |
| `UCURSOS_DESCARGAS` | `~/Downloads/U-Cursos` |

### Contribuir

Issues y pull requests bienvenidos. Reglas: solo lectura, nada de automatizar el login, y nada de datos de terceros (nombres, RUT, notas de otras personas) en el repo. Ver `CLAUDE.md`.
