"""Fakes standing in for DSS: a project, the API client and a dataset to write the recap to.

They copy the shape of the DSS answers the code expects. When a check on a real instance shows a
different shape (see docs/verification.md), fix the fake together with the code.
"""

from collections.abc import Iterator
from typing import Any, Optional

PROJECT_KEY = "TEST"


class FakeDatasetHandle:
    """Stands in for the dataset handle of the API: records the clear and answers what the test asked."""

    def __init__(self, project: "FakeProject", name: str) -> None:
        self.project = project
        self.name = name

    def clear(self) -> Any:
        self.project.cleared.append(self.name)
        answer = self.project.clear_answers.get(self.name, {"success": False, "messages": []})
        if isinstance(answer, Exception):
            raise answer
        return answer


class FakeSettings:
    def __init__(self, shared: dict[str, list[str]]) -> None:
        self.shared = shared

    def get_raw(self) -> dict[str, Any]:
        objects: list[dict[str, Any]] = [
            {"type": "DATASET", "localName": name, "rules": [{"targetProject": target} for target in targets]}
            for name, targets in self.shared.items()
        ]
        objects.append({"type": "SAVED_MODEL", "localName": "a_shared_model", "rules": [{"targetProject": "OTHER"}]})
        return {"exposedObjects": {"objects": objects}}


class FakeGraph:
    def __init__(self, without_recipe: list[str]) -> None:
        self.without_recipe = without_recipe

    def get_source_computables(self) -> list[dict[str, Any]]:
        nodes = [{"ref": name, "type": "COMPUTABLE_DATASET"} for name in self.without_recipe]
        nodes.append({"ref": "a_folder", "type": "COMPUTABLE_FOLDER"})
        return nodes


class FakeFlow:
    def __init__(self, project: "FakeProject") -> None:
        self.project = project

    def get_graph(self) -> FakeGraph:
        if self.project.flow_error:
            raise self.project.flow_error
        return FakeGraph(self.project.without_recipe)


class FakeGeneralSettings:
    """Stands in for the general settings of the instance: here, only its global tag categories."""

    def __init__(self, tag_categories: dict[str, list[str]]) -> None:
        self.tag_categories = tag_categories

    def get_raw(self) -> dict[str, Any]:
        categories = [
            {"name": name, "globalTags": [{"name": tag, "color": "#77bec2"} for tag in tags], "appliesTo": ["DATASET"]}
            for name, tags in self.tag_categories.items()
        ]
        return {"globalTagsCategories": categories}


class FakeProject:
    """Stands in for the project handle returned by dataiku.api_client().

    :param is_admin: the user is an administrator of the project, and can read its sharing
    :param project_tags: the project tag list. None: the tags of its datasets, as DSS fills it
    :param tag_categories: the global tag categories of the instance, with their tags
    :param is_instance_admin: the user is a DSS administrator, and can read the tag categories
    """

    def __init__(
        self,
        datasets: list[dict[str, Any]],
        shared: Optional[dict[str, list[str]]] = None,
        without_recipe: Optional[list[str]] = None,
        clear_answers: Optional[dict[str, Any]] = None,
        is_admin: bool = True,
        flow_error: Optional[Exception] = None,
        project_tags: Optional[list[str]] = None,
        tags_error: Optional[Exception] = None,
        tag_categories: Optional[dict[str, list[str]]] = None,
        is_instance_admin: bool = True,
    ) -> None:
        self.datasets = datasets
        self.shared = shared or {}
        self.without_recipe = without_recipe or []
        self.clear_answers = clear_answers or {}
        self.is_admin = is_admin
        self.flow_error = flow_error
        self.project_tags = project_tags
        self.tags_error = tags_error
        self.tag_categories = tag_categories or {}
        self.is_instance_admin = is_instance_admin
        self.cleared: list[str] = []

    @property
    def client(self) -> "FakeClient":
        """The client the project handle was made with, as DSSProject.client."""
        return FakeClient(self)

    def list_datasets(self) -> list[dict[str, Any]]:
        return self.datasets

    def get_settings(self) -> FakeSettings:
        if not self.is_admin:
            raise PermissionError("Action forbidden, you are not admin of this project")
        return FakeSettings(self.shared)

    def get_tags(self) -> dict[str, Any]:
        if self.tags_error:
            raise self.tags_error
        tags = self.project_tags
        if tags is None:
            tags = sorted({tag for dataset in self.datasets for tag in dataset.get("tags") or []})
        return {"tags": {tag: {} for tag in tags}}

    def get_flow(self) -> FakeFlow:
        return FakeFlow(self)

    def get_dataset(self, name: str) -> FakeDatasetHandle:
        return FakeDatasetHandle(self, name)


class FakeClient:
    """Stands in for dataiku.api_client()."""

    def __init__(self, project: FakeProject, login: str = "jdoe", auth_error: Optional[Exception] = None) -> None:
        self.project = project
        self.login = login
        self.auth_error = auth_error

    def get_auth_info(self) -> dict[str, Any]:
        if self.auth_error:
            raise self.auth_error
        return {"authIdentifier": self.login}

    def get_project(self, project_key: str) -> FakeProject:
        assert project_key == PROJECT_KEY
        return self.project

    def get_general_settings(self) -> FakeGeneralSettings:
        if not self.project.is_instance_admin:
            raise PermissionError("Action forbidden, you are not admin")
        return FakeGeneralSettings(self.project.tag_categories)


class FakeWriter:
    """Stands in for the writer of dataiku.Dataset: like DSS, closing it replaces the data, or adds
    the rows to it when spec_item["appendMode"] is true."""

    def __init__(self, dataset: "FakeRecapDataset") -> None:
        self.dataset = dataset
        self.append = bool(dataset.spec_item["appendMode"])
        self.rows: list[list[Any]] = []

    def __enter__(self) -> "FakeWriter":
        return self

    def __exit__(self, error_type: Any, error: Any, traceback: Any) -> None:
        if error_type is None:
            self.dataset.rows = self.dataset.rows + self.rows if self.append else self.rows

    def write_tuple(self, values: list[Any]) -> None:
        if self.dataset.write_error:
            raise self.dataset.write_error
        self.rows.append(list(values))


class FakeRecapDataset:
    """Stands in for dataiku.Dataset: keeps the schema and the rows written to it.

    Like dataiku.Dataset outside a recipe, spec_item["appendMode"] starts false. Reading the rows
    fails the test: the macros never read a recap dataset.
    """

    def __init__(
        self,
        columns: Optional[list[str]] = None,
        rows: Optional[list[list[Any]]] = None,
        write_error: Optional[Exception] = None,
    ) -> None:
        self.schema = [{"name": column, "type": "string"} for column in columns or []]
        self.rows = rows or []
        self.write_error = write_error
        self.spec_item: dict[str, Any] = {"appendMode": False}

    def read_schema(self, raise_if_empty: bool = True) -> list[dict[str, str]]:
        assert not raise_if_empty, "an empty recap dataset is expected, it must not raise"
        return self.schema

    def iter_tuples(self) -> Iterator[tuple[Any, ...]]:
        raise AssertionError("a recap dataset is never read: DSS appends the rows")

    def write_schema(self, columns: list[dict[str, str]]) -> None:
        self.schema = columns

    def get_writer(self) -> FakeWriter:
        return FakeWriter(self)


def make_dataset(
    name: str,
    tags: list[str],
    managed: bool = True,
    partitioned: bool = False,
    project_key: str = PROJECT_KEY,
) -> dict[str, Any]:
    """Return a dataset as project.list_datasets() lists it."""
    dimensions = [{"name": "day", "type": "time"}, {"name": "country", "type": "value"}] if partitioned else []
    return {
        "name": name,
        "type": "PostgreSQL",
        "tags": tags,
        "managed": managed,
        "projectKey": project_key,
        "params": {"connection": "pg_prod"},
        "partitioning": {"dimensions": dimensions},
    }
