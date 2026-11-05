"""Choices of the category tag lists of a macro form, for any macro that selects datasets by tags.

The logic is in python-lib, where it is tested without DSS.
"""

from typing import Any

import dataiku

from dss_maintenance.core.tags import list_category_tag_choices, read_listed_tag_categories


def do(payload: dict[str, Any], config: dict[str, Any], plugin_config: dict[str, Any], inputs: Any) -> dict[str, Any]:
    """Return the category tags on the datasets of the project the form is opened in, by category.

    The plugin setting "Tag categories" can limit them to some categories.
    """
    project_key = dataiku.default_project_key()
    project = dataiku.api_client().get_project(project_key)
    categories = read_listed_tag_categories(plugin_config)
    return {"choices": list_category_tag_choices(project, project_key, categories)}
