"""Tests of the import rules that keep the macros apart.

- The shared code (core, recap) never imports a macro.
- A macro never imports another macro.
- A runnable.py imports only its own macro and the shared code. A resource file, only the shared code.
- Nothing in python-lib imports dataiku, so that it can be tested without DSS.
- Imports are absolute, so that each rule can be read from the import itself.
"""

import ast
from pathlib import Path

import pytest

from support.dataiku_stub import RESOURCES, ROOT, RUNNABLES

LIB = ROOT / "python-lib"
PACKAGE = LIB / "dss_maintenance"
SHARED = ("dss_maintenance.core", "dss_maintenance.recap")
MACROS = "dss_maintenance.macros"


def imported_modules(path: Path) -> list[str]:
    """Return the modules a file imports. A relative import fails the test."""
    modules = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.relative_to(ROOT)}: use an absolute import"
            assert node.module
            modules.append(node.module)
    return modules


def is_under(module: str, *packages: str) -> bool:
    return any(module == package or module.startswith(package + ".") for package in packages)


def library_files() -> list[Path]:
    return sorted(PACKAGE.rglob("*.py"))


@pytest.mark.parametrize("path", library_files(), ids=lambda path: str(path.relative_to(LIB)))
def test_python_lib_never_imports_dataiku(path: Path) -> None:
    assert not [module for module in imported_modules(path) if is_under(module, "dataiku")]


@pytest.mark.parametrize(
    "path",
    [path for path in library_files() if path.relative_to(PACKAGE).parts[0] in ("core", "recap")],
    ids=lambda path: str(path.relative_to(LIB)),
)
def test_the_shared_code_never_imports_a_macro(path: Path) -> None:
    assert not [module for module in imported_modules(path) if is_under(module, MACROS)]


@pytest.mark.parametrize(
    "path",
    [path for path in library_files() if len(path.relative_to(PACKAGE).parts) > 2 and "macros" in path.parts],
    ids=lambda path: str(path.relative_to(LIB)),
)
def test_a_macro_never_imports_another_macro(path: Path) -> None:
    own = f"{MACROS}.{path.relative_to(PACKAGE).parts[1]}"
    other_macros = [
        module for module in imported_modules(path) if is_under(module, MACROS) and not is_under(module, own)
    ]
    assert not other_macros


@pytest.mark.parametrize("folder", sorted(path.parent.name for path in RUNNABLES.glob("*/runnable.py")))
def test_a_runnable_imports_only_its_macro_and_the_shared_code(folder: str) -> None:
    own = f"{MACROS}.{folder.replace('-', '_')}"
    modules = [
        module for module in imported_modules(RUNNABLES / folder / "runnable.py") if is_under(module, "dss_maintenance")
    ]

    assert own in modules
    assert all(is_under(module, own, *SHARED) for module in modules), modules


@pytest.mark.parametrize("path", sorted(RESOURCES.glob("*.py")), ids=lambda path: path.name)
def test_a_resource_file_imports_only_the_shared_code(path: Path) -> None:
    modules = [module for module in imported_modules(path) if is_under(module, "dss_maintenance")]

    assert all(is_under(module, *SHARED) for module in modules), modules
