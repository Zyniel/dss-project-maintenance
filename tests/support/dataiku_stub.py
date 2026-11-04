"""A fake dataiku package, to run the files DSS runs (runnable.py, resource files) without DSS."""

import importlib.util
import sys
import types
from pathlib import Path
from typing import Any, Optional

import pytest

from support.fakes import PROJECT_KEY, FakeClient, FakeRecapDataset

ROOT = Path(__file__).resolve().parents[2]
RUNNABLES = ROOT / "python-runnables"
RESOURCES = ROOT / "resource"


class Runnable:
    """Stands in for dataiku.runnables.Runnable, the base class of every runnable.py."""


def install_fake_dataiku(
    monkeypatch: pytest.MonkeyPatch, client: FakeClient, opened: Optional[list[Any]] = None
) -> None:
    """Put a fake dataiku package in sys.modules, until the end of the test.

    :param opened: receives (name, project_key, ignore_flow, dataset) for each dataiku.Dataset opened
    """

    def open_dataset(name: str, project_key: str = "", ignore_flow: bool = False) -> FakeRecapDataset:
        dataset = FakeRecapDataset()
        if opened is not None:
            opened.append((name, project_key, ignore_flow, dataset))
        return dataset

    dataiku = types.ModuleType("dataiku")
    runnables = types.ModuleType("dataiku.runnables")
    setattr(runnables, "Runnable", Runnable)  # noqa: B010
    setattr(dataiku, "runnables", runnables)  # noqa: B010
    setattr(dataiku, "api_client", lambda: client)  # noqa: B010
    setattr(dataiku, "default_project_key", lambda: PROJECT_KEY)  # noqa: B010
    setattr(dataiku, "Dataset", open_dataset)  # noqa: B010
    monkeypatch.setitem(sys.modules, "dataiku", dataiku)
    monkeypatch.setitem(sys.modules, "dataiku.runnables", runnables)


def load_module(path: Path) -> Any:
    """Load a Python file DSS runs, such as a runnable.py. Install the fake dataiku package first."""
    name = "_".join(path.relative_to(ROOT).with_suffix("").parts).replace("-", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_runnable_class(folder: str) -> Any:
    """Return the Runnable subclass of a macro folder, as DSS finds it. Install the fake dataiku package first."""
    module = load_module(RUNNABLES / folder / "runnable.py")
    classes = [value for value in vars(module).values() if isinstance(value, type) and issubclass(value, Runnable)]
    classes.remove(Runnable)
    assert len(classes) == 1, f"{folder}/runnable.py must define one Runnable"
    return classes[0]
