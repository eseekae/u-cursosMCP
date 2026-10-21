# Pruebas manuales en Claude Desktop

Guía para probar la extensión a mano. Hazlas en orden: cada una depende de la anterior.
Usa **un chat nuevo** para cada prueba, así Claude no arrastra lo anterior.

Al reportar un problema: qué escribiste, qué hizo Claude (qué tool llamó y qué devolvió) y qué esperabas.
**No pegues capturas con nombres, RUT o notas de otras personas.**

Si algo falla al arrancar, el log está en Claude Desktop: Configuración → Desarrollador (o Extensiones) → U-Cursos → abrir logs.

## 1. Instalación

- **Haz:** Configuración → Extensiones, arrastra `ucursos.mcpb` e instala.
- **Esperado:** aparece "U-Cursos (solo lectura)" activada, sin error. En un chat, el ícono de herramientas muestra 8 tools.
- **Anota:** cuánto tardó la primera vez y si salió algún error.

## 2. Login

- **Escribe:** `¿Tengo sesión activa en U-Cursos?`
- **Esperado:** Claude llama `iniciar_sesion` y se abre U-Cursos en tu navegador por defecto. Inicias sesión como siempre, le dices `listo` y Claude llama `estado_sesion`, importa tu sesión y confirma "Sesión activa".
- **Anota:** en qué navegador se abrió, si pudo importar la sesión (en Windows con Chrome o Edge muy nuevos puede fallar: prueba iniciar sesión en Firefox) y si Claude esperó tu aviso.

## 3. Mis cursos

- **Escribe:** `Lista mis cursos de U-Cursos de este semestre`
- **Esperado:** los mismos ramos que ves en la barra lateral de U-Cursos, con código y sección correctos.
- **Anota:** ramos que falten o sobren, y si los nombres salen con tildes bien (no `Ã³`).

## 4. Tareas

- **Escribe:** `¿Qué tareas tengo pendientes?` y después `Muéstrame todas, también las entregadas`
- **Esperado:** coincide con la página "Tareas" de U-Cursos: título, ramo, fecha límite y estado.
- **Anota:** cualquier diferencia. Este parser está sin validar con HTML real, así que es probable que falle.

## 5. Material docente y descarga

- **Escribe:** `¿Qué material docente hay en <ramo>?` y luego `Descarga <nombre de un archivo>`
- **Esperado:** la lista coincide con la página del ramo. El archivo queda en `Descargas/U-Cursos` y se abre bien (nombre con tildes incluido).
- **Anota:** si faltan archivos, si salen las categorías como si fueran archivos, o si la descarga queda corrupta.

## 6. Leer material

- **Escribe:** `Lee <nombre de un PDF del ramo> y hazme un resumen` y después `¿En qué página habla de <tema>?`
- **Esperado:** Claude llama `leer_material`, resume lo que dice el archivo y cita páginas que coinciden con el PDF real. Si el archivo es largo, lo pide por partes.
- **Prueba también:** un Word, un PowerPoint y, si hay, un PDF escaneado (debería decir que no tiene texto, no inventar).

## 7. Novedades y notas

- **Escribe:** `Muéstrame las últimas 3 novedades de <ramo>` y `¿Cómo voy con las notas de <ramo>?` (uno con notas publicadas)
- **Esperado:** títulos, fechas y texto igual que en U-Cursos; las notas como tabla con las mismas evaluaciones.
- **Anota:** diferencias. El parser de novedades también está sin validar.

## 8. Sesión guardada

- **Haz:** cierra Claude Desktop por completo (también desde la bandeja del sistema), ábrelo y en un chat nuevo escribe `¿Qué tareas tengo pendientes?`
- **Esperado:** responde directo, sin pedirte login otra vez.

## 9. Casos raros

- **Escribe:** `Muéstrame las notas de MA9999` (un ramo que no existe)
  - **Esperado:** Claude dice que no lo encuentra; no se cae ni inventa notas.
- **Escribe:** `Publica "hola" en el foro de <ramo>`
  - **Esperado:** Claude dice que no puede, porque el MCP es solo de lectura.

## Plantilla de reporte

```
Prueba N:
Resultado: OK / Falla
Qué escribí:
Qué hizo Claude (tool y respuesta):
Qué esperaba:
```
