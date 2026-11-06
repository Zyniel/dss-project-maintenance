"""Select the datasets of a project by their tags.

A macro form that selects datasets by tags starts with included_scope ("Include"):

- TAGS: the datasets with the included tags. At least one included tag is needed;
- ALL_DATASETS: every dataset of the project. The included tags are ignored.

Then come two lists, included and excluded, of three fields each:

- included_tags, excluded_tags: tags typed by hand;
- included_category_tags, excluded_category_tags: category tags picked from a list (see resource/tag_choices.py);
- included_match, excluded_match: ANY or ALL.

Among the selected datasets, the ones matching the excluded tags are excluded. Without excluded tags,
none is excluded.
"""

from typing import Any, NamedTuple, Optional

from dss_project_maintenance.core.project import list_project_datasets

# How a list of tags matches a dataset: when it carries any of them, or all of them.
MATCH_ANY = "ANY"
MATCH_ALL = "ALL"

# Which datasets "Include" selects, with the label and the choices of the form. A test checks the form.
SCOPE_TAGS = "TAGS"
SCOPE_ALL_DATASETS = "ALL_DATASETS"
SCOPE_LABEL = "Include"
SCOPE_CHOICES = {SCOPE_TAGS: "Datasets with the included tags", SCOPE_ALL_DATASETS: "All datasets"}


class TagSelection(NamedTuple):
    """The tags of the form, each list merged from its two fields."""

    included_tags: list[str]  # Empty with SCOPE_ALL_DATASETS.
    included_match: str
    excluded_tags: list[str]
    excluded_match: str
    included_scope: str = SCOPE_TAGS


class TaggedDataset(NamedTuple):
    """A selected dataset, with the tags of each list it carries."""

    dataset: dict[str, Any]
    included_tags: list[str]
    excluded_tags: list[str]
    is_excluded: bool


def read_tag_list(config: dict[str, Any], *keys: str) -> list[str]:
    """Return the tags of one list of the form, merged from its fields, as DSS stores them on a dataset.

    The manual field holds free text. The category field holds tags picked from the list, which DSS
    stores as "category:value". Matching is exact and case-sensitive.
    """
    tags: list[str] = []
    for key in keys:
        values = config.get(key) or []
        if isinstance(values, str):
            values = [values]  # Without this, the loop below would go through its letters.
        for value in values:
            tag = str(value or "").strip()
            if tag and tag not in tags:
                tags.append(tag)
    return tags


def read_match(config: dict[str, Any], key: str) -> str:
    """Return how a list of tags matches. Missing, it matches any tag, as the form does by default.

    :raises ValueError: if the value is neither ANY nor ALL
    """
    match = config.get(key) or MATCH_ANY
    if match not in (MATCH_ANY, MATCH_ALL):
        raise ValueError(f"{key} must be {MATCH_ANY} or {MATCH_ALL}, not {match!r}.")
    return str(match)


def read_scope(config: dict[str, Any]) -> str:
    """Return which datasets "Include" selects. Missing, the datasets with the included tags, as the form does.

    :raises ValueError: if the value is neither TAGS nor ALL_DATASETS
    """
    scope = config.get("included_scope") or SCOPE_TAGS
    if not isinstance(scope, str) or scope not in SCOPE_CHOICES:
        raise ValueError(f"included_scope must be {SCOPE_TAGS} or {SCOPE_ALL_DATASETS}, not {scope!r}.")
    return scope


def read_tag_selection(config: dict[str, Any]) -> TagSelection:
    """Return which datasets "Include" selects, the included and excluded tags, and how each list matches.

    With "All datasets", the included tags are ignored: see ignored_included_tags(). A tag in both
    lists does not stop the run: the excluded tags still apply, which is the safe side. See tags_in_both().

    :raises ValueError: if "Include" asks for the included tags and there is none
    """
    scope = read_scope(config)
    included_tags = read_tag_list(config, "included_tags", "included_category_tags") if scope == SCOPE_TAGS else []
    if scope == SCOPE_TAGS and not included_tags:
        all_datasets = SCOPE_CHOICES[SCOPE_ALL_DATASETS]
        raise ValueError(f"Give at least one included tag, or choose '{all_datasets}' in '{SCOPE_LABEL}'.")
    return TagSelection(
        included_tags,
        read_match(config, "included_match"),
        read_tag_list(config, "excluded_tags", "excluded_category_tags"),
        read_match(config, "excluded_match"),
        scope,
    )


def ignored_included_tags(config: dict[str, Any], selection: TagSelection) -> list[str]:
    """Return the included tags of the form that "All datasets" ignores.

    The form hides the included tags with "All datasets", but keeps their values: the macro tells the user.
    """
    if selection.included_scope != SCOPE_ALL_DATASETS:
        return []
    return read_tag_list(config, "included_tags", "included_category_tags")


def matches(dataset_tags: list[str], tags: list[str], match: str) -> bool:
    """Tell whether a dataset carries any of the tags, or all of them."""
    if match == MATCH_ALL:
        return all(tag in dataset_tags for tag in tags)
    return any(tag in dataset_tags for tag in tags)


def describe_match(kind: str, match: str) -> str:
    """Return why a dataset matches a list of tags, such as "Has included tags" or "Has all excluded tags"."""
    return f"Has all {kind} tags" if match == MATCH_ALL else f"Has {kind} tags"


def tags_in_both(selection: TagSelection) -> list[str]:
    """Return the tags in both lists. They are excluded: the macro tells the user to check the lists."""
    return [tag for tag in selection.included_tags if tag in selection.excluded_tags]


def count_datasets_with_tag(datasets: list[dict[str, Any]], tag: str) -> int:
    """Return the number of datasets carrying this tag."""
    return sum(1 for dataset in datasets if tag in (dataset.get("tags") or []))


def is_included(dataset_tags: list[str], selection: TagSelection) -> bool:
    """Tell whether "Include" selects a dataset: always with "All datasets", else if it matches the included tags."""
    if selection.included_scope == SCOPE_ALL_DATASETS:
        return True
    # An empty list selects nothing. matches() would select every dataset with ALL: all([]) is true.
    return bool(selection.included_tags) and matches(dataset_tags, selection.included_tags, selection.included_match)


def select_datasets(datasets: list[dict[str, Any]], selection: TagSelection) -> list[TaggedDataset]:
    """Return the datasets "Include" selects, in the order given.

    An excluded dataset is returned too, with is_excluded set, so that the recap can list it.
    """
    selected = []
    for dataset in datasets:
        dataset_tags = dataset.get("tags") or []
        if not is_included(dataset_tags, selection):
            continue
        is_excluded = bool(selection.excluded_tags) and matches(
            dataset_tags, selection.excluded_tags, selection.excluded_match
        )
        selected.append(
            TaggedDataset(
                dataset,
                [tag for tag in dataset_tags if tag in selection.included_tags],
                [tag for tag in dataset_tags if tag in selection.excluded_tags],
                is_excluded,
            )
        )
    return selected


def split_category_tag(tag: str) -> tuple[str, str]:
    """Return the category and the value of a tag: "Stage:Raw" gives ("Stage", "Raw"), "tmp" gives ("", "tmp")."""
    category, colon, value = tag.partition(":")
    return (category, value) if colon else ("", tag)


def read_listed_tag_categories(plugin_config: Optional[dict[str, Any]]) -> Optional[set[str]]:
    """Return the tag categories the category tag lists offer, from the plugin settings, or None for all.

    The setting "Tag categories" holds category names, such as Stage. An entry typed like a tag,
    such as "Stage:" or "Stage:Raw", means its category. Matching is exact and case-sensitive, like
    the tags. Empty, every category is offered.
    """
    entries = read_tag_list(plugin_config or {}, "listed_tag_categories")
    return {split_category_tag(entry)[0] or entry for entry in entries} or None


def list_category_tag_choices(
    project: Any, project_key: str, categories: Optional[set[str]] = None
) -> list[dict[str, str]]:
    """Return the choices of the category tag lists of the form: the category tags on this project's datasets.

    DSS stores a category tag as "category:value". Each goes in the group of its category. A tag on
    no dataset would select nothing, so it is not offered.

    :param categories: only the tags of these categories, from read_listed_tag_categories(); all if None
    """
    tags = {
        str(tag)
        for dataset in list_project_datasets(project, project_key)
        for tag in dataset.get("tags") or []
        if ":" in str(tag) and (categories is None or split_category_tag(str(tag))[0] in categories)
    }

    def sort_key(tag: str) -> tuple[str, str]:
        return (split_category_tag(tag)[0].lower(), tag.lower())

    return [{"value": tag, "label": tag, "group": split_category_tag(tag)[0]} for tag in sorted(tags, key=sort_key)]
