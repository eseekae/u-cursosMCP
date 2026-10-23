"""
Entrada del ejecutable único (PyInstaller). Ver .github/workflows/release.yml y README.md.

Se usa un archivo aparte porque PyInstaller no puede usar como script un módulo con imports
relativos (ucursos_mcp/launcher.py).
"""

from ucursos_mcp.launcher import main

if __name__ == "__main__":
    main()
