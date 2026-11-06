"""Tests of the macro form, runnable.json: its parameters agree with the code."""

import json
from typing import Any

from dss_project_maintenance.macros.report_dataset_tags import MACRO
from dss_project_maintenance.macros.report_dataset_tags.report import OPTION_DEFAULTS, OPTION_LABELS
from support.dataiku_stub import RUNNABLES

# The parameters of the form, top to bottom.
OPTION_PARAMS = ["show_unused_tags", "aggregate_by_tag"]
RECAP_PARAMS = ["recap_to_dataset", "recap_dataset", "recap_append", "on_recap_error"]


def read_form() -> dict[str, Any]:
    form: dict[str, Any] = json.loads((RUNNABLES / MACRO.id / "runnable.json").read_text(encoding="utf-8"))
    return form


def named_params(form: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {param["name"]: param for param in form["params"] if "name" in param}


def test_the_parameters_in_their_order() -> None:
    form = read_form()

    assert list(named_params(form)) == OPTION_PARAMS + RECAP_PARAMS
    # A report changes nothing: no "Simulate", and no "Run" section with "If an error occurs".
    assert "simulate" not in named_params(form)
    assert "on_error" not in named_params(form)
    assert [param["label"] for param in form["params"] if param["type"] == "SEPARATOR"] == ["Summary"]


def test_project_readers_can_run_it() -> None:
    assert read_form()["permissions"] == ["READ_CONF"]


def test_option_defaults_and_labels_match_the_code() -> None:
    params = named_params(read_form())

    for option, default in OPTION_DEFAULTS.items():
        assert params[option]["defaultValue"] is default, option
    for option, label in OPTION_LABELS.items():
        assert params[option]["label"] == label, option
