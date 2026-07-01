"""Verificación de la arquitectura hexagonal del proyecto.

Comprueba que las capas internas no importen de las capas externas:
  domain      → no importa ninguna otra capa src.*
  application → no importa adapters, agent, app, infrastructure
  adapters    → no importa application, agent, app
"""

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src"

# Regla: capa → capas prohibidas
RULES: dict[str, list[str]] = {
    "domain": ["application", "adapters", "agent", "app", "infrastructure"],
    "application": ["adapters", "agent", "app", "infrastructure"],
    "adapters": ["application", "agent", "app"],
}


def get_imports(path: Path) -> list[str]:
    """Extrae los módulos importados de un fichero Python."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except SyntaxError:
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module)
    return modules


def check_layer(layer: str, forbidden: list[str]) -> list[str]:
    """Devuelve violaciones encontradas en la capa dada."""
    violations: list[str] = []
    layer_dir = SRC / layer
    if not layer_dir.exists():
        return violations

    for py_file in layer_dir.rglob("*.py"):
        for module in get_imports(py_file):
            for banned in forbidden:
                is_src_banned = (
                    module.startswith(f"src.{banned}.") or module == f"src.{banned}"
                )
                is_rel_banned = module.startswith(f"{banned}.")
                if is_src_banned or is_rel_banned:
                    rel = py_file.relative_to(ROOT)
                    violations.append(
                        f"  {rel}: importa '{module}' (prohibido en '{layer}')"
                    )
    return violations


def main() -> None:
    all_violations: list[str] = []
    for layer, forbidden in RULES.items():
        all_violations.extend(check_layer(layer, forbidden))

    if all_violations:
        print("FALLO — violaciones de arquitectura detectadas:")
        for v in all_violations:
            print(v)
        sys.exit(1)
    else:
        print("OK — sin violaciones de arquitectura.")


if __name__ == "__main__":
    main()
