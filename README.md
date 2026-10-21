# ucursos-mcp

Servidor MCP **de solo lectura** para que Claude lea tu U-Cursos (Universidad de Chile): cursos, tareas, notas, novedades y el contenido del material docente (PDF, Word y PowerPoint).

No es oficial ni está afiliado a la Universidad. Es open source (MIT): úsalo, modifícalo y mejóralo.

## Instalar en Claude Desktop (sin terminal)

1. Descarga `ucursos.mcpb` desde la última versión en [Releases](https://github.com/eseekae/u-cursosMCP/releases).
2. En Claude Desktop: **Configuración → Extensiones** y arrastra el archivo (o haz doble clic sobre él).
3. Pulsa **Instalar**. La primera vez tarda un poco: Claude Desktop descarga Python y las librerías.
4. En un chat nuevo, pídele: *"Revisa mis cursos de U-Cursos"*.
5. Claude abre U-Cursos en tu navegador de siempre. Inicia sesión ahí como cualquier día y avísale cuando ya estés dentro; Claude importa tu sesión.

Listo. Cuando la sesión expire, Claude vuelve a abrir U-Cursos para que entres de nuevo.

Funciona con Edge, Chrome, Firefox, Brave, Opera o Vivaldi: basta con que inicies sesión en U-Cursos en el que uses normalmente.

### Qué puedes pedirle

- "¿Qué tareas tengo pendientes esta semana?"
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
| `iniciar_sesion()` | Abre U-Cursos en tu navegador para que entres |
| `estado_sesion()` | Importa la sesión del navegador y dice si quedó activa |
| `listar_cursos()` | Cursos inscritos, con su `path` |
| `tareas(solo_pendientes=True)` | Tareas de todos los cursos |
| `notas(curso_path)` | Tablas de notas del curso |
| `material_docente(curso_path)` | Lista de material |
| `leer_material(curso_path, descarga, desde=0)` | Texto de un PDF, .docx, .pptx o archivo de texto, por partes |
| `descargar_material(curso_path, descarga)` | Baja un archivo a `Descargas/U-Cursos` |
| `novedades(curso_path, limite=10)` | Últimos anuncios |

## Para desarrolladores

### Arquitectura

```
auth.py         Importa la sesión desde tu navegador (browser_cookie3); abre U-Cursos con webbrowser
client.py       Sesión HTTP con esas cookies, decodifica Latin-1, detecta sesión expirada
parsers.py      HTML -> modelos (única capa que conoce el HTML de U-Cursos)
documentos.py   archivo -> texto (PDF, .docx, .pptx, texto)
models.py       DTOs con pydantic
server.py       Tools MCP (MCPServer del SDK mcp 2.x, transporte stdio)
mcpb_server.py  Punto de entrada de la extensión de Claude Desktop
manifest.json   Manifest de la extensión (.mcpb, runtime uv)
```

El login de U-Cursos pasa por Cuenta UChile (OAuth2/OIDC con captcha), así que no se automatiza: el usuario inicia sesión en su propio navegador y el MCP lee esa sesión. Se reutiliza hasta que expire.

### Correr desde el código

```powershell
git clone https://github.com/eseekae/u-cursosMCP.git
cd u-cursosMCP
uv venv
uv pip install -e ".[dev]"
uv run pytest -q                              # tests
uv run ucursos-login                          # abre U-Cursos y, tras entrar, importa la sesión (opcional)
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
| `UCURSOS_BROWSER` | el navegador del que leer la sesión (por defecto los prueba todos) |
| `UCURSOS_DESCARGAS` | `~/Downloads/U-Cursos` |

### Contribuir

Issues y pull requests bienvenidos. Reglas: solo lectura, nada de automatizar el login, y nada de datos de terceros (nombres, RUT, notas de otras personas) en el repo. Ver `CLAUDE.md`.
