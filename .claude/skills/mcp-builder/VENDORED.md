# Origen de esta skill

Copiada sin modificar desde https://github.com/anthropics/skills (carpeta `skills/mcp-builder`), licencia Apache 2.0 (ver `LICENSE.txt`). Copiada el 19/10/2026.

Ajustes para este proyecto:

- Se omitió `reference/node_mcp_server.md` porque el proyecto es solo Python. Los links a la guía de TypeScript en `SKILL.md` no aplican.
- La skill habla de **FastMCP**. Este proyecto usa el **SDK `mcp` 2.x**, donde FastMCP pasó a llamarse `MCPServer` (`from mcp.server.mcpserver import MCPServer`). Los decoradores `@mcp.tool()` funcionan igual. Si un ejemplo de la skill no calza con la versión 2.x, manda la API instalada (revisar con `python -c "import mcp.server.mcpserver as m; help(m.MCPServer)"`).

Para actualizarla: volver a copiar la carpeta desde el repo de Anthropic y mantener este archivo.
