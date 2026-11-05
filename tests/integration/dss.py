"""Helpers of the integration tests: fill a scratch project, run a macro and read its recap, on a real DSS.

Each function takes handles of the DSS API client (`dataikuapi`). See docs/integration-tests.md.
"""

import io
import json
import re
from typing import Any

PLUGIN_ID = "project-maintenance"
CLEAR = f"pyrunnable_{PLUGIN_ID}_clear-datasets-by-tags"
REPORT = f"pyrunnable_{PLUGIN_ID}_report-dataset-tags"

# Every scratch project starts with this prefix: a test never touches another project.
PROJECT_PREFIX = "DSSPM_IT_"

# The data of each test dataset: 3 rows.
CSV = b"id,amount\n1,10\n2,20\n3,30\n"
ROW_COUNT = 3


def dss_error() -> Any:
    """Return the exception of the DSS API client for an error of DSS, such as a macro run that fails."""
    from dataikuapi.utils import DataikuException

    return DataikuException


def set_tags(dataset: Any, tags: list[str]) -> None:
    """Set the tags of a dataset."""
    settings = dataset.get_settings()
    settings.get_raw()["tags"] = tags
    settings.save()


def add_uploaded_dataset(project: Any, name: str, tags: list[str]) -> None:
    """Add an uploaded dataset with 3 rows. DSS lists it as not managed: the macro never clears it."""
    dataset = project.create_upload_dataset(name)
    dataset.uploaded_add_file(io.BytesIO(CSV), f"{name}.csv")
    dataset.autodetect_settings().save()
    set_tags(dataset, tags)


def add_built_dataset(project: Any, name: str, tags: list[str], connection: str) -> None:
    """Add a managed dataset with 3 rows, built by a recipe from an uploaded dataset with no tag.

    This is the dataset the macro clears by default: DSS manages its data, and a recipe can build it again.
    """
    source = f"{name}_source"
    add_uploaded_dataset(project, source, [])
    builder = project.new_recipe("sync")
    builder.with_input(source)
    builder.with_new_output(name, connection)
    builder.create()
    dataset = project.get_dataset(name)
    dataset.build(wait=True)
    set_tags(dataset, tags)


def add_empty_dataset(project: Any, name: str, connection: str, columns: tuple[str, ...] = ()) -> None:
    """Add a managed dataset with no data, such as a summary dataset, with these text columns."""
    dataset = project.new_managed_dataset(name).with_store_into(connection).create()
    if columns:
        dataset.set_schema({"columns": [{"name": column, "type": "string"} for column in columns]})


def count_rows(project: Any, name: str) -> int:
    """Return the number of rows of a dataset. A cleared dataset has no data at all: 0 rows."""
    try:
        return sum(1 for _ in project.get_dataset(name).iter_rows())
    except Exception as error:
        # After a clear, DSS 13.4.4 answers "Root path of the dataset <name> does not exist".
        if "does not exist" in str(error):
            return 0
        raise


def read_recap(html: str) -> dict[str, Any]:
    """Return the JSON recap of the hidden block of an HTML result."""
    block = re.search(r'<script type="application/json" id="dtp-recap-data">(.*?)</script>', html, re.DOTALL)
    assert block, "The result of the macro has no JSON recap."
    recap: dict[str, Any] = json.loads(block.group(1))
    return recap


def run_macro(project: Any, macro_id: str, params: dict[str, Any]) -> dict[str, Any]:
    """Run a macro, wait for its end, and return its JSON recap. A run that fails raises an exception."""
    macro = project.get_macro(macro_id)
    run_id = macro.run(params=params, wait=True)
    html = macro.get_result(run_id, as_type="string")
    return read_recap(html.decode("utf-8") if isinstance(html, bytes) else html)


def row_of(recap: dict[str, Any], name: str) -> dict[str, Any]:
    """Return the recap row of a dataset of Clear Datasets by Tags."""
    rows: list[dict[str, Any]] = [row for row in recap["datasets"] if row["name"] == name]
    assert len(rows) == 1, f"{name} is not once in the recap: {[row['name'] for row in recap['datasets']]}"
    return rows[0]


def give_access(project: Any, client: Any, write: bool) -> Any:
    """Give the user of a client access to a scratch project, and return the project as this user sees it."""
    login = client.get_auth_info()["authIdentifier"]
    permissions = project.get_permissions()
    permissions["permissions"].append({"user": login, "readProjectContent": True, "writeProjectContent": write})
    project.set_permissions(permissions)
    return client.get_project(project.project_key)


def list_macro_ids(project: Any) -> set[str]:
    """Return the ids of the macros the user of this project handle sees."""
    return {macro["runnableType"] for macro in project.list_macros()}


def add_macro_scenario(project: Any, scenario_id: str, macro_id: str, params: dict[str, Any]) -> Any:
    """Add a scenario with one step: run a macro with these values of its form."""
    scenario = project.create_scenario(scenario_id, "step_based")
    settings = scenario.get_settings()
    settings.get_raw()["params"]["steps"] = [
        {
            "id": "run_macro",
            "type": "runnable",
            "name": "Run the macro",
            "params": {"runnableType": macro_id, "config": params, "adminConfig": {}},
        }
    ]
    settings.save()
    return scenario
