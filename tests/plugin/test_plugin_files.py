"""Tests of the plugin files, run on every macro: a new macro gets them without writing a test.

For each folder of python-runnables, they check its runnable.json and its runnable.py against the
macro package of the same name. They also check plugin.json, the resource files and the plugin zip.
"""

import importlib
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

import pytest

from dss_project_maintenance.core.macro import MaintenanceMacro
from dss_project_maintenance.core.options import (
    RECAP_ERROR_CHOICES,
    RECAP_OPTION_DEFAULTS,
    RECAP_OPTION_LABELS,
    RUN_ERROR_CHOICES,
    RUN_OPTION_DEFAULTS,
    RUN_OPTION_LABELS,
)
from dss_project_maintenance.recap.html import AG_GRID_DEFAULT_INTEGRITY, AG_GRID_DEFAULT_URL
from support.dataiku_stub import RESOURCES, ROOT, RUNNABLES, install_fake_dataiku, load_module, load_runnable_class
from support.fakes import PROJECT_KEY, FakeClient, FakeProject, make_dataset

PLUGIN_ID = "project-maintenance"
# The heading of the macros of the plugin on the Macros page of a project.
CATEGORY = "Project maintenance"
# The options of the "Run" section, only in the forms of the macros that change data.
RUN_PARAMS = ["on_error"]
# The options every form ends with, in its "Summary" section.
RECAP_PARAMS = ["recap_to_dataset", "recap_dataset", "recap_append", "on_recap_error"]
# The options shown only when "Write to a dataset" is checked.
RECAP_DATASET_PARAMS = ["recap_dataset", "recap_append", "on_recap_error"]
# The visibility conditions of the forms: "model.<checkbox>", or "model.<select list> != '<one of its choices>'".
VISIBILITY_CONDITION = re.compile(r"model\.(\w+)(?: != '(\w+)')?")
# The select lists of what to do on errors, with their choices.
ERROR_CHOICE_PARAMS = {"on_error": RUN_ERROR_CHOICES, "on_recap_error": RECAP_ERROR_CHOICES}

MACRO_FOLDERS = sorted(path.name for path in RUNNABLES.iterdir() if path.is_dir() and path.name != "__pycache__")
MACRO_PACKAGES = sorted(
    path.name
    for path in (ROOT / "python-lib" / "dss_project_maintenance" / "macros").iterdir()
    if (path / "__init__.py").is_file()
)


def read_json(path: Any) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def macro_of(folder: str) -> MaintenanceMacro:
    """Return the MACRO of the package named after a folder of python-runnables."""
    module = importlib.import_module(f"dss_project_maintenance.macros.{folder.replace('-', '_')}")
    macro: MaintenanceMacro = module.MACRO
    return macro


def named_params(form: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {param["name"]: param for param in form["params"] if "name" in param}


# plugin.json


def test_plugin_id_and_versions() -> None:
    plugin = read_json(ROOT / "plugin.json")
    project_text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")

    assert plugin["id"] == PLUGIN_ID
    assert f'\nversion = "{plugin["version"]}"\n' in project_text


def test_the_plugin_settings_default_to_the_ag_grid_of_the_code() -> None:
    settings = named_params(read_json(ROOT / "plugin.json"))

    assert settings["ag_grid_url"]["defaultValue"] == AG_GRID_DEFAULT_URL
    assert settings["ag_grid_integrity"]["defaultValue"] == AG_GRID_DEFAULT_INTEGRITY


def test_the_plugin_settings_list_every_tag_category_by_default() -> None:
    settings = named_params(read_json(ROOT / "plugin.json"))

    assert (settings["listed_tag_categories"]["type"], settings["listed_tag_categories"]["defaultValue"]) == (
        "STRINGS",
        [],
    )


# Each macro


def test_each_macro_folder_has_its_macro_package_and_back() -> None:
    assert MACRO_FOLDERS
    assert [folder.replace("-", "_") for folder in MACRO_FOLDERS] == MACRO_PACKAGES


@pytest.mark.parametrize("folder", MACRO_FOLDERS)
def test_the_form_describes_its_macro(folder: str) -> None:
    form = read_json(RUNNABLES / folder / "runnable.json")
    macro = macro_of(folder)

    assert macro.id == folder
    assert form["meta"]["label"] == macro.label
    assert form["meta"]["category"] == CATEGORY
    assert form["meta"]["description"] and form["meta"]["icon"]
    assert form["impersonate"] is True  # The macro acts with the rights of the user who runs it.
    assert form["permissions"]
    assert form["resultType"] == "HTML"
    assert form["macroRoles"] == [{"type": "PROJECT_MACROS"}]
    if "paramsPythonSetup" in form:
        assert (RESOURCES / form["paramsPythonSetup"]).is_file()


def separators_of(form: dict[str, Any]) -> list[str]:
    return [param["label"] for param in form["params"] if param["type"] == "SEPARATOR"]


def check_defaults_and_labels(
    params: dict[str, dict[str, Any]], defaults: dict[str, Any], labels: dict[str, str]
) -> None:
    for option, default in defaults.items():
        value = params[option]["defaultValue"]
        assert (value, type(value)) == (default, type(default)), option
    for option, label in labels.items():
        assert params[option]["label"] == label, option


@pytest.mark.parametrize("folder", MACRO_FOLDERS)
def test_the_form_ends_with_the_recap_options(folder: str) -> None:
    form = read_json(RUNNABLES / folder / "runnable.json")
    params = named_params(form)

    assert list(params)[-len(RECAP_PARAMS) :] == RECAP_PARAMS
    assert separators_of(form)[-1] == "Summary"
    check_defaults_and_labels(params, RECAP_OPTION_DEFAULTS, RECAP_OPTION_LABELS)
    assert params["recap_dataset"]["type"] == "DATASET"
    for name in RECAP_DATASET_PARAMS:
        assert params[name]["visibilityCondition"] == "model.recap_to_dataset", name


@pytest.mark.parametrize("folder", MACRO_FOLDERS)
def test_the_error_choices_are_select_lists_with_the_choices_of_the_code(folder: str) -> None:
    params = named_params(read_json(RUNNABLES / folder / "runnable.json"))

    for name, choices in ERROR_CHOICE_PARAMS.items():
        if name in params:
            assert (params[name]["type"], params[name]["mandatory"]) == ("SELECT", True), name
            expected = [{"value": value, "label": label} for value, label in choices.items()]
            assert params[name]["selectChoices"] == expected, name


@pytest.mark.parametrize("folder", MACRO_FOLDERS)
def test_only_a_macro_that_changes_data_has_the_run_options(folder: str) -> None:
    form = read_json(RUNNABLES / folder / "runnable.json")
    params = named_params(form)
    changes_data = "simulate" in params

    assert ("on_error" in params) is changes_data
    assert ("Run" in separators_of(form)) is changes_data
    if changes_data:
        assert list(params)[-len(RUN_PARAMS + RECAP_PARAMS) :] == RUN_PARAMS + RECAP_PARAMS
        assert separators_of(form)[-2:] == ["Run", "Summary"]
        check_defaults_and_labels(params, RUN_OPTION_DEFAULTS, RUN_OPTION_LABELS)


@pytest.mark.parametrize("folder", MACRO_FOLDERS)
def test_the_form_parameters_are_well_formed(folder: str) -> None:
    form = read_json(RUNNABLES / folder / "runnable.json")
    params = named_params(form)

    assert len(params) == len([param for param in form["params"] if "name" in param])
    for param in form["params"]:
        if param["type"] in ("STRINGS", "MULTISELECT"):
            # Each list gets its own empty default: a DSS form once sent the value of one list in another.
            assert param.get("defaultValue") == [], param["name"]
        condition = param.get("visibilityCondition")
        if condition:
            match = VISIBILITY_CONDITION.fullmatch(condition)
            assert match and match.group(1) in params, condition
            if match.group(2):
                choices = [choice["value"] for choice in params[match.group(1)]["selectChoices"]]
                assert match.group(2) in choices, condition


@pytest.mark.parametrize("folder", MACRO_FOLDERS)
def test_the_runnable_loads_in_dss(folder: str, monkeypatch: pytest.MonkeyPatch) -> None:
    install_fake_dataiku(monkeypatch, FakeClient(FakeProject([])))

    runnable = load_runnable_class(folder)(PROJECT_KEY, {}, {})

    assert runnable.get_progress_target() == (100, "NONE")


# Resource files


def test_each_resource_file_answers_dss() -> None:
    for path in RESOURCES.glob("*.py"):
        assert "\ndef do(payload" in path.read_text(encoding="utf-8"), path.name


def test_the_category_tag_lists_offer_the_category_tags_of_the_project(monkeypatch: pytest.MonkeyPatch) -> None:
    project = FakeProject([make_dataset("a", ["tmp", "Stage:Raw"]), make_dataset("b", ["Stage:Clean", "tmp"])])
    install_fake_dataiku(monkeypatch, FakeClient(project))

    module = load_module(RESOURCES / "tag_choices.py")

    assert module.do({}, {}, {}, []) == {
        "choices": [
            {"value": "Stage:Clean", "label": "Stage:Clean", "group": "Stage"},
            {"value": "Stage:Raw", "label": "Stage:Raw", "group": "Stage"},
        ]
    }


def test_the_plugin_settings_limit_the_category_tag_lists(monkeypatch: pytest.MonkeyPatch) -> None:
    project = FakeProject([make_dataset("a", ["Stage:Raw", "Owner:ops"]), make_dataset("b", ["Other:x"])])
    install_fake_dataiku(monkeypatch, FakeClient(project))

    module = load_module(RESOURCES / "tag_choices.py")

    choices = module.do({}, {}, {"listed_tag_categories": ["Stage", "Owner"]}, [])["choices"]
    assert [choice["value"] for choice in choices] == ["Owner:ops", "Stage:Raw"]


# The plugin zip


def test_plugin_zip_builds_from_any_folder(tmp_path: Path) -> None:
    version = read_json(ROOT / "plugin.json")["version"]
    zip_path = ROOT / "dist" / f"dss-plugin-{PLUGIN_ID}-{version}.zip"
    zip_path.unlink(missing_ok=True)

    subprocess.run([sys.executable, str(ROOT / "build_plugin_zip.py")], cwd=tmp_path, check=True, capture_output=True)

    assert zip_path.is_file()
    assert not (tmp_path / "dist").exists()
    with zipfile.ZipFile(zip_path) as plugin_zip:
        assert "plugin.json" in plugin_zip.namelist()


def test_plugin_zip_holds_the_plugin_and_nothing_else() -> None:
    subprocess.run([sys.executable, str(ROOT / "build_plugin_zip.py")], cwd=ROOT, check=True, capture_output=True)
    version = read_json(ROOT / "plugin.json")["version"]

    with zipfile.ZipFile(ROOT / "dist" / f"dss-plugin-{PLUGIN_ID}-{version}.zip") as plugin_zip:
        names = plugin_zip.namelist()

    assert "plugin.json" in names
    assert "LICENSE" in names
    for folder in MACRO_FOLDERS:
        assert f"python-runnables/{folder}/runnable.json" in names
        assert f"python-runnables/{folder}/runnable.py" in names
        assert f"python-lib/dss_project_maintenance/macros/{folder.replace('-', '_')}/__init__.py" in names
    assert "python-lib/dss_project_maintenance/core/runner.py" in names
    assert "resource/tag_choices.py" in names
    assert {name.split("/")[0] for name in names} == {
        "plugin.json",
        "README.md",
        "LICENSE",
        "python-lib",
        "python-runnables",
        "resource",
    }
    assert not [name for name in names if "__pycache__" in name]
