"""Tests of the macro form, runnable.json: its parameters agree with the code."""

import json
from typing import Any

from dss_maintenance.core.tags import MATCH_ALL, MATCH_ANY, SCOPE_ALL_DATASETS, SCOPE_CHOICES, SCOPE_LABEL, SCOPE_TAGS
from dss_maintenance.macros.clear_datasets_by_tags import MACRO
from dss_maintenance.macros.clear_datasets_by_tags.cleanup import OPTION_DEFAULTS, OPTION_LABELS
from support.dataiku_stub import RUNNABLES

# The parameters of the form, top to bottom.
INCLUDED_TAG_PARAMS = ["included_tags", "included_category_tags", "included_match"]
TAG_PARAMS = ["included_scope", *INCLUDED_TAG_PARAMS]
TAG_PARAMS += ["excluded_tags", "excluded_category_tags", "excluded_match"]
OPTION_PARAMS = ["simulate", "purge_shared", "purge_partitioned", "purge_without_recipe"]
COMMON_PARAMS = ["on_error", "recap_to_dataset", "recap_dataset", "recap_append", "on_recap_error"]


def read_form() -> dict[str, Any]:
    form: dict[str, Any] = json.loads((RUNNABLES / MACRO.id / "runnable.json").read_text(encoding="utf-8"))
    return form


def named_params(form: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {param["name"]: param for param in form["params"] if "name" in param}


def test_the_parameters_in_their_order() -> None:
    form = read_form()

    assert list(named_params(form)) == TAG_PARAMS + OPTION_PARAMS + COMMON_PARAMS
    assert form["params"][0]["name"] == "included_scope"  # "Include" and the tags come first, in no section.
    assert form["permissions"] == ["WRITE_CONF"]
    assert form["paramsPythonSetup"] == "tag_choices.py"


def test_each_tag_list_starts_from_its_own_empty_list() -> None:
    # A DSS form once sent a tag picked in one list in both: each list gets its own default.
    params = named_params(read_form())

    for name in ["included_tags", "excluded_tags"]:
        assert (params[name]["type"], params[name]["defaultValue"]) == ("STRINGS", [])
    for name in ["included_category_tags", "excluded_category_tags"]:
        param = params[name]
        assert (param["type"], param["getChoicesFromPython"], param["disableAutoReload"]) == ("MULTISELECT", True, True)
        assert param["defaultValue"] == []
    for name in ["included_match", "excluded_match"]:
        assert [choice["value"] for choice in params[name]["selectChoices"]] == [MATCH_ANY, MATCH_ALL]
        assert params[name]["defaultValue"] == MATCH_ANY


def test_option_defaults_and_labels_match_the_code() -> None:
    params = named_params(read_form())

    for option, default in OPTION_DEFAULTS.items():
        assert params[option]["defaultValue"] is default, option
    for option, label in OPTION_LABELS.items():
        assert params[option]["label"] == label, option


def test_include_has_the_choices_of_the_code_and_hides_the_included_tags() -> None:
    params = named_params(read_form())
    scope = params["included_scope"]

    assert (scope["type"], scope["label"], scope["defaultValue"], scope["mandatory"]) == (
        "SELECT",
        SCOPE_LABEL,
        SCOPE_TAGS,
        True,
    )
    assert scope["selectChoices"] == [{"value": value, "label": label} for value, label in SCOPE_CHOICES.items()]
    # "!=": a form without the value, such as one DSS remembered from 1.x, still shows the tags.
    for name in INCLUDED_TAG_PARAMS:
        assert params[name]["visibilityCondition"] == f"model.included_scope != '{SCOPE_ALL_DATASETS}'", name
