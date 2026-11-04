"""Tests of the options of the form: their safe defaults."""

from typing import Any

import pytest

from dss_maintenance.core.options import RECAP_OPTION_DEFAULTS, RUN_OPTION_DEFAULTS
from dss_maintenance.macros.clear_datasets_by_tags.cleanup import OPTION_DEFAULTS, read_options
from support.fakes import PROJECT_KEY


def test_options_default_to_a_simulation_that_clears_shared_datasets_only() -> None:
    options = read_options({}, PROJECT_KEY)

    assert options == {**OPTION_DEFAULTS, **RUN_OPTION_DEFAULTS, **RECAP_OPTION_DEFAULTS, "recap_dataset": None}
    assert options["simulate"] is True
    assert options["purge_shared"] is True
    assert not options["purge_partitioned"] and not options["purge_without_recipe"]


@pytest.mark.parametrize("option", ["purge_partitioned", "purge_without_recipe"])
@pytest.mark.parametrize("value", [None, "true", 1, "yes"])
def test_only_a_real_true_clears_partitioned_or_recipe_less_datasets(option: str, value: Any) -> None:
    assert read_options({option: value}, PROJECT_KEY)[option] is False


@pytest.mark.parametrize("value", [None, "false", 0, "no"])
def test_only_a_real_false_skips_shared_datasets(value: Any) -> None:
    assert read_options({"purge_shared": value}, PROJECT_KEY)["purge_shared"] is True


@pytest.mark.parametrize("value", [None, "false", 0, "no"])
def test_only_a_real_false_ends_the_simulation(value: Any) -> None:
    assert read_options({"simulate": value}, PROJECT_KEY)["simulate"] is True


def test_the_run_and_recap_options_are_read_too() -> None:
    options = read_options({"on_error": "FAIL", "recap_dataset": "recap"}, PROJECT_KEY)

    assert (options["on_error"], options["recap_dataset"], options["on_recap_error"]) == ("FAIL", "recap", "CONTINUE")
