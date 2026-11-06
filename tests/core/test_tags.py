"""Tests of selecting datasets by tags: "Include", the two lists of the form, any or all, the category tag choices."""

from typing import Any

import pytest

from dss_project_maintenance.core.tags import (
    MATCH_ALL,
    MATCH_ANY,
    SCOPE_ALL_DATASETS,
    SCOPE_TAGS,
    TagSelection,
    describe_match,
    ignored_included_tags,
    list_category_tag_choices,
    matches,
    read_listed_tag_categories,
    read_tag_list,
    read_tag_selection,
    select_datasets,
    split_category_tag,
    tags_in_both,
)
from support.fakes import PROJECT_KEY, FakeProject, make_dataset

# Reading the form


def test_manual_tags_and_category_tags_are_merged() -> None:
    config = {"included_tags": ["temporary"], "included_category_tags": ["Department:Marketing"]}
    assert read_tag_list(config, "included_tags", "included_category_tags") == ["temporary", "Department:Marketing"]


def test_tags_are_trimmed_and_deduplicated() -> None:
    config = {"included_tags": [" a ", "a", "b:c", ""], "included_category_tags": ["b:c", None]}
    assert read_tag_list(config, "included_tags", "included_category_tags") == ["a", "b:c"]


def test_a_single_text_is_one_tag_and_not_its_letters() -> None:
    assert read_tag_list({"included_tags": "purge"}, "included_tags") == ["purge"]


def test_both_lists_are_read_with_how_they_match() -> None:
    config = {
        "included_tags": ["a"],
        "included_category_tags": ["Stage:Raw"],
        "included_match": "ALL",
        "excluded_tags": ["k"],
        "excluded_category_tags": ["Stage:Gold"],
    }

    assert read_tag_selection(config) == TagSelection(["a", "Stage:Raw"], MATCH_ALL, ["k", "Stage:Gold"], MATCH_ANY)


def test_an_empty_excluded_list_excludes_nothing() -> None:
    assert read_tag_selection({"included_tags": ["a"]}).excluded_tags == []


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"included_tags": ["", " "], "excluded_category_tags": []},
        {"excluded_category_tags": ["Stage:Gold"]},  # In 1.x, this selected every other dataset.
        {"included_scope": SCOPE_TAGS, "excluded_tags": ["k"]},
    ],
)
def test_the_included_tags_need_at_least_one_tag(config: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match=r"^Give at least one included tag, or choose 'All datasets' in 'Include'\.$"):
        read_tag_selection(config)


@pytest.mark.parametrize("value", [None, ""])
def test_include_defaults_to_the_included_tags(value: Any) -> None:
    assert read_tag_selection({"included_scope": value, "included_tags": ["a"]}).included_scope == SCOPE_TAGS


@pytest.mark.parametrize("value", ["all", "ALL", "TAGS ", 1, ["ALL_DATASETS"]])
def test_include_is_tags_or_all_datasets(value: Any) -> None:
    with pytest.raises(ValueError, match="included_scope must be TAGS or ALL_DATASETS"):
        read_tag_selection({"included_scope": value, "included_tags": ["a"]})


def test_all_datasets_needs_no_tag() -> None:
    selection = read_tag_selection({"included_scope": SCOPE_ALL_DATASETS})

    assert selection == TagSelection([], MATCH_ANY, [], MATCH_ANY, SCOPE_ALL_DATASETS)


def test_all_datasets_ignores_the_included_tags_and_names_them() -> None:
    # The form hides the included tags with "All datasets", but still sends their values.
    config = {
        "included_scope": SCOPE_ALL_DATASETS,
        "included_tags": ["a"],
        "included_category_tags": ["Stage:Raw"],
        "excluded_tags": ["a"],
    }

    selection = read_tag_selection(config)

    assert (selection.included_tags, selection.excluded_tags) == ([], ["a"])
    assert ignored_included_tags(config, selection) == ["a", "Stage:Raw"]
    assert tags_in_both(selection) == []


def test_no_included_tag_is_ignored_with_the_included_tags() -> None:
    config = {"included_tags": ["a"]}
    assert ignored_included_tags(config, read_tag_selection(config)) == []


def test_a_tag_in_both_lists_does_not_stop_reading_the_form() -> None:
    selection = read_tag_selection({"included_category_tags": ["Stage:Raw"], "excluded_category_tags": ["Stage:Raw"]})

    assert selection.included_tags == selection.excluded_tags == ["Stage:Raw"]
    assert tags_in_both(selection) == ["Stage:Raw"]


@pytest.mark.parametrize("value", ["any", "both", 1])
def test_a_match_is_any_or_all(value: Any) -> None:
    with pytest.raises(ValueError, match="included_match must be ANY or ALL"):
        read_tag_selection({"included_tags": ["a"], "included_match": value})


# Matching


@pytest.mark.parametrize(
    ("dataset_tags", "match", "expected"),
    [
        (["a"], MATCH_ANY, True),
        (["a"], MATCH_ALL, False),
        (["b", "a", "x"], MATCH_ALL, True),
        (["x"], MATCH_ANY, False),
    ],
)
def test_matches_any_or_all_tags(dataset_tags: list[str], match: str, expected: bool) -> None:
    assert matches(dataset_tags, ["a", "b"], match) is expected


@pytest.mark.parametrize("dataset_tag", ["TEMPORARY", "temporary2", "Stage", "Raw", "Stage:raw"])
def test_matching_is_exact_and_case_sensitive(dataset_tag: str) -> None:
    assert not matches([dataset_tag], ["temporary", "Stage:Raw"], MATCH_ANY)


@pytest.mark.parametrize(
    ("tag", "expected"),
    [("Stage:Raw", ("Stage", "Raw")), ("tmp", ("", "tmp")), ("a:b:c", ("a", "b:c")), (":x", ("", "x"))],
)
def test_split_category_tag(tag: str, expected: tuple[str, str]) -> None:
    assert split_category_tag(tag) == expected


def test_describe_match() -> None:
    assert describe_match("included", MATCH_ANY) == "Has included tags"
    assert describe_match("excluded", MATCH_ALL) == "Has all excluded tags"


# Selecting


def test_included_tags_select_and_excluded_tags_flag() -> None:
    datasets = [
        make_dataset("included_only", ["tmp", "other"]),
        make_dataset("both", ["keep", "tmp"]),
        make_dataset("neither", ["other"]),
    ]
    selection = TagSelection(["tmp"], MATCH_ANY, ["keep"], MATCH_ANY)

    selected = select_datasets(datasets, selection)

    assert [(tagged.dataset["name"], tagged.is_excluded) for tagged in selected] == [
        ("included_only", False),
        ("both", True),
    ]
    assert (selected[1].included_tags, selected[1].excluded_tags) == (["tmp"], ["keep"])


@pytest.mark.parametrize(
    ("excluded_tags", "expected"),
    [([], [("untagged", False), ("gold", False)]), (["Stage:Gold"], [("untagged", False), ("gold", True)])],
)
def test_all_datasets_selects_every_dataset(excluded_tags: list[str], expected: list[tuple[str, bool]]) -> None:
    datasets = [make_dataset("untagged", []), make_dataset("gold", ["Stage:Gold"])]

    selected = select_datasets(datasets, TagSelection([], MATCH_ANY, excluded_tags, MATCH_ANY, SCOPE_ALL_DATASETS))

    assert [(tagged.dataset["name"], tagged.is_excluded) for tagged in selected] == expected


@pytest.mark.parametrize("match", [MATCH_ANY, MATCH_ALL])
def test_an_empty_included_list_selects_nothing(match: str) -> None:
    # all([]) is true: without this rule, ALL would select every dataset.
    datasets = [make_dataset("untagged", []), make_dataset("tagged", ["a"])]

    assert select_datasets(datasets, TagSelection([], match, [], MATCH_ANY)) == []


def test_all_excluded_tags_exclude_only_the_datasets_carrying_every_one() -> None:
    datasets = [make_dataset("both", ["k1", "k2"]), make_dataset("one", ["k1"])]

    selected = select_datasets(datasets, TagSelection([], MATCH_ANY, ["k1", "k2"], MATCH_ALL, SCOPE_ALL_DATASETS))

    assert [tagged.is_excluded for tagged in selected] == [True, False]


# Choices of the category tag lists


def test_category_tag_choices_are_the_category_tags_of_the_project_grouped_by_category() -> None:
    project = FakeProject(
        [
            make_dataset("a", ["tmp", "Stage:Raw", "archive"]),
            make_dataset("b", ["Stage:Clean", "tmp", "owner:ops"]),
            make_dataset("c", []),
            make_dataset("shared_in", ["Stage:Foreign"], project_key="OTHER"),
        ]
    )

    choices = list_category_tag_choices(project, PROJECT_KEY)

    assert [(choice["group"], choice["value"]) for choice in choices] == [
        ("owner", "owner:ops"),
        ("Stage", "Stage:Clean"),
        ("Stage", "Stage:Raw"),
    ]
    assert all(choice["label"] == choice["value"] for choice in choices)


def test_a_project_without_category_tags_offers_no_choice() -> None:
    assert list_category_tag_choices(FakeProject([make_dataset("a", ["tmp"])]), PROJECT_KEY) == []


def test_the_category_tag_lists_can_be_limited_to_some_categories() -> None:
    project = FakeProject(
        [
            make_dataset("a", ["tmp", "Stage:Raw", "Owner:ops"]),
            make_dataset("b", ["Stage:Clean", "stage:lower", "Other:x"]),
        ]
    )

    choices = list_category_tag_choices(project, PROJECT_KEY, {"Stage", "Owner"})

    assert [choice["value"] for choice in choices] == ["Owner:ops", "Stage:Clean", "Stage:Raw"]


@pytest.mark.parametrize(
    ("plugin_config", "expected"),
    [
        (None, None),
        ({}, None),
        ({"listed_tag_categories": []}, None),
        ({"listed_tag_categories": ["", " "]}, None),
        ({"listed_tag_categories": [" Stage ", "Owner", "Stage"]}, {"Stage", "Owner"}),
        ({"listed_tag_categories": "Stage"}, {"Stage"}),
        # An entry typed like a tag means its category.
        ({"listed_tag_categories": ["Stage:", "Owner:ops", "Other"]}, {"Stage", "Owner", "Other"}),
    ],
)
def test_read_listed_tag_categories(plugin_config: Any, expected: Any) -> None:
    assert read_listed_tag_categories(plugin_config) == expected
