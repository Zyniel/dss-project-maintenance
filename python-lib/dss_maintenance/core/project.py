"""Read a DSS project: its datasets, what it shares with other projects, and its Flow."""

from typing import Any


def list_project_datasets(project: Any, project_key: str) -> list[dict[str, Any]]:
    """Return the datasets owned by this project.

    Datasets shared by other projects are left out here, so that no macro ever handles them.
    """
    project_datasets = []
    for dataset in project.list_datasets():
        if dataset["projectKey"] == project_key:
            project_datasets.append(dataset)
    return project_datasets


def read_shared_datasets(project: Any) -> dict[str, list[str]]:
    """Return the datasets this project shares with other projects, with the projects they are shared with.

    DSS only gives this list to project administrators: for other users, this raises.
    """
    project_settings = project.get_settings().get_raw()

    shared_datasets = {}
    for shared_object in project_settings["exposedObjects"]["objects"]:
        if shared_object["type"] == "DATASET":
            target_projects = {rule.get("targetProject") or "" for rule in shared_object.get("rules") or []}
            shared_datasets[shared_object["localName"]] = sorted(target_projects - {""})
    return shared_datasets


def read_datasets_without_recipe(project: Any) -> set[str]:
    """Return the datasets no recipe builds: nothing in the Flow can rebuild their data."""
    graph = project.get_flow().get_graph()
    return {node["ref"] for node in graph.get_source_computables() if node["type"] == "COMPUTABLE_DATASET"}


def name_projects(shared_with: list[str]) -> str:
    """Return "A, B", the projects a dataset is shared with, or "other projects" when DSS names none."""
    return ", ".join(shared_with) or "other projects"
