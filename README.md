# ucursos-mcp

Servidor MCP **de solo lectura** para que Claude lea tu U-Cursos (Universidad de Chile): cursos, tareas (con su enunciado y adjuntos), notas, novedades y el contenido del material docente (PDF, Word y PowerPoint).

No es oficial ni está afiliado a la Universidad. Es open source (MIT): úsalo, modifícalo y mejóralo.

## Instalar en ChatGPT, Claude o Cursor (doble clic, sin terminal)

1. Descarga el archivo de tu sistema desde la última versión en [Releases](https://github.com/eseekae/u-cursosMCP/releases): `ucursos-mcp-windows.exe` o `ucursos-mcp-linux` (Mac, por ahora, con la extensión o el código fuente).
2. Haz **doble clic**. Marca en qué apps quieres usarlo (ChatGPT de escritorio y Codex, Claude Desktop, Cursor) y pulsa **Instalar**.
3. Cuando te pregunte si quieres iniciar sesión en U-Cursos, di que sí: se abre una ventana, entras como siempre y se cierra sola.
4. Cierra del todo tu app y ábrela de nuevo. Pídele: *"Revisa mis cursos de U-Cursos"*.

**¿Ya lo tenías instalado?** Descarga la versión nueva y vuelve a hacer doble clic: actualiza la anterior en el mismo lugar, no tienes que desinstalar nada ni tocar la configuración de ChatGPT. Si la app estaba abierta, ciérrala y ábrela de nuevo para que cargue la versión nueva. Tu sesión de U-Cursos se conserva.

Qué hace al instalarse: copia el programa a una carpeta fija (`%LOCALAPPDATA%\ucursos-mcp` en Windows, `~/.local/share/ucursos-mcp` en Linux) y agrega una entrada `ucursos` en la config de cada app, dejando un respaldo `.ucursos.bak` del archivo original. Para quitarlo, ejecuta `ucursos-mcp uninstall`.

Avisos normales por ser un programa sin firma digital:
- **Windows:** SmartScreen dice "Windows protegió su PC". Pulsa **Más información → Ejecutar de todas formas**.
- Si prefieres no ejecutar binarios, usa la extensión de Claude Desktop o corre el código fuente (ver abajo).

## Instalar en Claude Desktop (extensión .mcpb)

1. Descarga `ucursos.mcpb` desde la última versión en [Releases](https://github.com/eseekae/u-cursosMCP/releases).
2. En Claude Desktop: **Configuración → Extensiones** y arrastra el archivo (o haz doble clic sobre él).
3. Pulsa **Instalar**. La primera vez tarda un poco: Claude Desktop descarga Python y las librerías.
4. En un chat nuevo, pídele: *"Revisa mis cursos de U-Cursos"*.

## Cómo inicias sesión

Es siempre igual y lo hace Claude por ti: cuando haga falta, **se abre una ventana de U-Cursos**. Escribes tu clave y resuelves el captcha como cualquier día, y la ventana se cierra sola. No tienes que avisarle nada ni elegir navegador. Cuando la sesión expire, vuelve a abrirse la ventana.

- **Tu clave nunca pasa por Claude ni por este programa**: la escribes tú en la ventana, como en un navegador. El programa solo mira que ya hayas entrado y guarda la sesión en tu computador.
- En Windows la ventana usa WebView2 (viene con Edge y con Windows 11). Si en tu equipo no se puede abrir, Claude usa **tu navegador de siempre**: te pide entrar ahí y lee esa sesión. Con Firefox, Zen o LibreWolf funciona siempre; con Edge, Chrome o Brave en Windows puede fallar porque cifran sus cookies, y ahí te sugiere usar Firefox o Zen.
- También puedes entrar tú sin esperar a Claude: `ucursos-mcp login` (o `uv run ucursos-login` desde el código fuente).
- Para cerrar la sesión por completo, borra la carpeta `~/.ucursos-mcp/` (en Windows, `%USERPROFILE%\.ucursos-mcp`).

### Qué puedes pedirle

- "¿Qué tareas tengo pendientes esta semana?"
- "¿Qué entregué en Programación y con qué nota?"
- "¿De qué se trata la tarea 3 de Programación? Lee el enunciado"
- "Muéstrame solo las ayudantías de Cálculo"
- "Muéstrame las últimas novedades de Cálculo"
- "¿Qué material docente hay en Física?"
- "Lee la guía 3 de Física y explícame el ejercicio 2"
- "¿Qué entra en el control 2 de Cálculo?"
- "¿Cómo voy con las notas de Álgebra?"

## Seguridad y privacidad

- **Tu clave nunca pasa por el código ni por Claude**: inicias sesión tú, en una ventana donde haces todo a mano (clave y captcha). El programa solo mira si ya entraste y guarda la sesión. No se automatiza ningún navegador ni se evade el captcha.
- Solo se guardan las cookies de la sesión y el perfil de la ventana de inicio de sesión, en tu computador (`~/.ucursos-mcp/`). No se envían a ningún servidor aparte de U-Cursos.
- Ninguna tool entrega tareas, publica ni modifica nada en U-Cursos.
- Solo lee los cursos en que estás inscrito.
- Los enunciados, comentarios, novedades y archivos se le entregan a Claude como datos, con un aviso de que no son instrucciones: si un enunciado trae texto dirigido a Claude, no lo sigue y te avisa.
- Los archivos descargados quedan en tu carpeta `Descargas/U-Cursos`.

## Tools

| Tool | Qué hace |
|---|---|
| `iniciar_sesion(navegador=None)` | Abre una ventana de U-Cursos para que entres (con `navegador`, lo abre en ese navegador como plan B) |
| `estado_sesion(navegador=None, perfil=None)` | Espera a que termines de entrar y confirma la sesión (con `navegador`, la importa de ese navegador y, si falla, explica qué encontró) |
| `listar_cursos()` | Cursos inscritos, con su `path` |
| `tareas(curso_path=None, solo_pendientes=True, desde=None, hasta=None, solo_semestre_actual=True)` | Tareas con curso, `id`, plazo ISO 8601 (hora de Chile) y estado normalizado (pendiente, entregada, atrasada, cerrada), ordenadas por plazo |
| `detalle_tarea(curso_path, tarea_id)` | Enunciado, apertura y cierre, estado, nota, comentarios, adjuntos y archivos entregados |
| `notas(curso_path)` | Tablas de notas del curso |
| `material_docente(curso_path, categoria=None)` | Lista de material con su categoría (Ayudantías, Pautas, Clases...) |
| `leer_material(curso_path, descarga, desde=0)` | Texto de un PDF, .docx, .pptx o archivo de texto (material o adjunto de tarea), por partes |
| `descargar_material(curso_path, descarga)` | Baja un archivo (material o adjunto de tarea) a `Descargas/U-Cursos` |
| `novedades(curso_path, limite=10)` | Últimos anuncios, con texto completo y enlaces |
| `presentacion_curso(curso_path)` | Presentación del ramo (programa, equipo docente, horario, evaluación) y las secciones que tiene el curso |
| `leer_seccion(curso_path, seccion, ruta=None, desde=0, limite=20)` | Cualquier otra sección: calendario, foro, clases, enlaces, material de alumnos, asistencias, archivos de comunidades... Con `ruta` abre un tema del foro o un evento |
| `horario()` | Tu horario semanal con todos tus cursos |

Si una sección no existe o da 403 (por ejemplo en una comunidad), el error dice qué secciones sí tiene ese curso. `leer_seccion` no abre correo, encuestas ni integrantes (la lista de integrantes trae datos de todo el curso), ni sigue links que ejecutan acciones.

## Para desarrolladores

### Arquitectura

```
navegadores.py  Navegadores conocidos, sus perfiles, el navegador por defecto y cómo abrir uno
auth.py         Guarda la sesión; lee las cookies de cada perfil (plan B), las valida y arma el diagnóstico
login_ventana.py  Ventana de inicio de sesión (pywebview): el usuario entra a mano, se guardan las cookies
client.py       Sesión HTTP con esas cookies, decodifica Latin-1, detecta sesión expirada
parsers.py      HTML -> modelos (única capa que conoce el HTML de U-Cursos)
documentos.py   archivo -> texto (PDF, .docx, .pptx, texto)
models.py       DTOs con pydantic
server.py       Tools MCP (MCPServer del SDK mcp 2.x, transporte stdio)
launcher.py     Punto de entrada: server MCP (stdio) o, con doble clic en el ejecutable, instalador
ventana.py      Preguntas del doble clic: dónde instalar y si iniciar sesión ahora (ventana o consola)
instalador.py   Registra (o actualiza) el server en ChatGPT/Codex (TOML), Claude Desktop y Cursor (JSON), con respaldo
mcpb_server.py  Punto de entrada de la extensión de Claude Desktop
ucursos_exe.py  Script que PyInstaller empaqueta en el ejecutable único
manifest.json   Manifest de la extensión (.mcpb, runtime uv)
```

El login de U-Cursos pasa por Cuenta UChile (OAuth2/OIDC con captcha), así que el código no lo automatiza: un humano hace todo. Hay dos caminos, en este orden:

1. **Ventana** (`login_ventana.py`, camino habitual). Corre en un proceso aparte (`ucursos-mcp ventana-login`) porque pywebview necesita el hilo principal y el server usa stdio. Solo mira la URL; al llegar a `/usuario/<hash>/` lee las cookies de la ventana, las valida contra U-Cursos y las guarda. La ventana y el server se hablan por el archivo de sesión y el código de salida (`SALIDA_*`). Dependencia solo en Windows (`pywebview`, que usa WebView2).
2. **Navegador del usuario** (plan B, `auth.py`). Si la ventana no está disponible o el usuario pide un `navegador`, `iniciar_sesion` abre U-Cursos ahí y `estado_sesion` lee las cookies de `u-cursos.cl` y `uchile.cl` de cada perfil y prueba cada uno contra U-Cursos (vale si redirige a `/usuario/<hash>/`; no se depende del nombre de ninguna cookie). Firefox, Zen y LibreWolf se leen con SQLite (copiando también `cookies.sqlite-wal`, donde quedan las cookies recién creadas); los Chromium, con browser_cookie3. El diagnóstico de la última falla queda en `~/.ucursos-mcp/login.log` (solo nombres de cookies, nunca valores).

Se guarda el origen de la sesión (`ventana` o navegador y perfil) y se reutiliza hasta que expire.

### Correr desde el código

```powershell
git clone https://github.com/eseekae/u-cursosMCP.git
cd u-cursosMCP
uv venv
uv pip install -e ".[dev]"
uv run pytest -q                              # tests
uv run ucursos-login                          # abre la ventana de inicio de sesión (opcional; --navegador zen --perfil X usa tu navegador)
uv run mcp dev src/ucursos_mcp/server.py      # MCP Inspector
```

**Claude Code:** abre Claude Code dentro de la carpeta del repo; `.mcp.json` ya registra el server `ucursos`.

**Fixtures:** `uv run python scripts/capturar_html.py <ruta> <nombre>` guarda dos versiones: `tests/fixtures/<nombre>.html` (casi completa, ignorada por git: trae tus ramos y datos de otros) y `tests/fixtures/esqueletos/<nombre>.html` (solo estructura: el texto escrito por personas queda como "xxxx" y los códigos de curso como CURSO1). Solo se suben los esqueletos; ábrelos en el navegador antes de commitear. `--esqueleto` rehace los esqueletos de lo que ya tengas descargado.

### Armar la extensión

```bash
npx @anthropic-ai/mcpb pack . ucursos.mcpb
```

El workflow `.github/workflows/release.yml` la arma y la adjunta sola al crear un tag `v*`.

### Probar un pull request

Cada PR corre los tests y arma la extensión. Para probarla sin esperar un release:

1. En el PR, pestaña **Checks** → *Release extensión* → **Summary**, baja el artefacto `ucursos-mcpb` (es un `.zip` con `ucursos.mcpb` adentro).
2. Instálalo en Claude Desktop como en la sección de arriba (reemplaza la versión anterior).
3. Sigue [`PRUEBAS.md`](PRUEBAS.md) y reporta en el PR con la plantilla del final.

Si un parser falla, captura la página con `scripts/capturar_html.py` y sigue la skill `arreglar-parser`.

### Variables de entorno

| Variable | Default |
|---|---|
| `UCURSOS_DATA` | `~/.ucursos-mcp` |
| `UCURSOS_SESSION` | `~/.ucursos-mcp/ucursos.storage_state.json` |
| `UCURSOS_BROWSER` | fuerza un navegador para el plan B (abrir y leer la sesión): `edge`, `chrome`, `brave`, `vivaldi`, `opera`, `opera_gx`, `chromium`, `firefox`, `zen`, `librewolf` (por defecto: el último que funcionó, luego el por defecto, luego todos) |
| `UCURSOS_DESCARGAS` | `~/Downloads/U-Cursos` |

### Contribuir

Issues y pull requests bienvenidos. Reglas: solo lectura, nada de automatizar el login (la ventana de inicio de sesión la maneja un humano), y nada de datos de terceros (nombres, RUT, notas de otras personas) en el repo. Ver `CLAUDE.md`.
