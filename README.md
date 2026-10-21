# ucursos-mcp

Servidor MCP **de solo lectura** para que Claude lea tu U-Cursos (Universidad de Chile): cursos, tareas, notas, material docente y novedades.

No es oficial ni está afiliado a la Universidad. Es open source (MIT): úsalo, modifícalo y mejóralo.

## Instalar en Claude Desktop (sin terminal)

1. Descarga `ucursos.mcpb` desde la última versión en [Releases](https://github.com/eseekae/u-cursosMCP/releases).
2. En Claude Desktop: **Configuración → Extensiones** y arrastra el archivo (o haz doble clic sobre él).
3. Pulsa **Instalar**. La primera vez tarda un poco: Claude Desktop descarga Python y las librerías.
4. En un chat nuevo, pídele: *"Revisa mis cursos de U-Cursos"*.
5. Claude va a abrir una ventana de Edge o Chrome. Inicia sesión ahí con tu cuenta UChile y avísale cuando termines.

Listo. Cuando la sesión expire, Claude te vuelve a abrir la ventana.

Necesitas Microsoft Edge (viene con Windows) o Google Chrome instalado.

### Qué puedes pedirle

- "¿Qué tareas tengo pendientes esta semana?"
- "Muéstrame las últimas novedades de Cálculo"
- "¿Qué material docente hay en Física?"
- "¿Cómo voy con las notas de Álgebra?"

## Seguridad y privacidad

- **Tu clave nunca pasa por el código ni por Claude**: la escribes tú en la ventana del navegador.
- Solo se guardan las cookies de la sesión, en tu computador (`~/.ucursos-mcp/`). No se envían a ningún servidor aparte de U-Cursos.
- Ninguna tool entrega tareas, publica ni modifica nada en U-Cursos.
- Los archivos descargados quedan en tu carpeta `Descargas/U-Cursos`.

## Tools

| Tool | Qué hace |
|---|---|
| `iniciar_sesion()` | Abre Edge o Chrome para que entres a U-Cursos |
| `estado_sesion()` | Dice si la sesión sigue activa |
| `listar_cursos()` | Cursos inscritos, con su `path` |
| `tareas(solo_pendientes=True)` | Tareas de todos los cursos |
| `notas(curso_path)` | Tablas de notas del curso |
| `material_docente(curso_path)` | Lista de material |
| `descargar_material(curso_path, descarga)` | Baja un archivo a `Descargas/U-Cursos` |
| `novedades(curso_path, limite=10)` | Últimos anuncios |

## Para desarrolladores

### Arquitectura

```
auth.py         Login manual con navegador visible (Playwright + Edge/Chrome instalado)
client.py       Sesión HTTP con esas cookies, decodifica Latin-1, detecta sesión expirada
parsers.py      HTML -> modelos (única capa que conoce el HTML de U-Cursos)
models.py       DTOs con pydantic
server.py       Tools MCP (MCPServer del SDK mcp 2.x, transporte stdio)
mcpb_server.py  Punto de entrada de la extensión de Claude Desktop
manifest.json   Manifest de la extensión (.mcpb, runtime uv)
```

El login de U-Cursos pasa por Cuenta UChile (OAuth2/OIDC con reCAPTCHA), así que no se automatiza: el usuario inicia sesión a mano y se reutiliza la sesión hasta que expire.

### Correr desde el código

```powershell
git clone https://github.com/eseekae/u-cursosMCP.git
cd u-cursosMCP
uv venv
uv pip install -e ".[dev]"
uv run pytest -q                              # tests
uv run ucursos-login                          # login desde la terminal (opcional)
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
| `UCURSOS_BROWSER_CHANNEL` | prueba `msedge` y luego `chrome` |
| `UCURSOS_DESCARGAS` | `~/Downloads/U-Cursos` |

### Contribuir

Issues y pull requests bienvenidos. Reglas: solo lectura, nada de automatizar el login, y nada de datos de terceros (nombres, RUT, notas de otras personas) en el repo. Ver `CLAUDE.md`.
