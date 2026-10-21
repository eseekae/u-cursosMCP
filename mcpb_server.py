"""
Punto de entrada de la extensión de Claude Desktop (.mcpb).

Claude Desktop corre `uv run --directory <extensión> mcpb_server.py`: uv instala Python y las
dependencias de pyproject.toml, y este archivo solo arranca el server del paquete.
"""

import sys
from pathlib import Path

# Respaldo por si uv no instaló el paquete: lo importamos directo desde src/.
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from ucursos_mcp.server import main  # noqa: E402

if __name__ == "__main__":
    main()
