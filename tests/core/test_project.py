"""Tests of reading a project: its datasets, its sharing and its Flow."""

import pytest

from dss_project_maintenance.core.project import (
    list_project_datasets,
    name_projects,
    read_datasets_without_recipe,
    read_shared_datasets,
)
from support.fakes import PROJECT_KEY, FakeProject, make_dataset


def test_datasets_shared_by_other_projects_are_left_out() -> None:
    project = FakeProject([make_dataset("local", []), make_dataset("foreign", [], project_key="OTHER")])

    assert [dataset["name"] for dataset in list_project_datasets(project, PROJECT_KEY)] == ["local"]


def test_shared_datasets_name_their_projects_and_other_objects_are_ignored() -> None:
    project = FakeProject([], shared={"sales": ["PROJ_C", "PROJ_B"], "anon": [""]})

    assert read_shared_datasets(project) == {"sales": ["PROJ_B", "PROJ_C"], "anon": []}


def test_only_project_administrators_can_read_the_sharing() -> None:
    with pytest.raises(PermissionError):
        read_shared_datasets(FakeProject([], is_admin=False))


def test_datasets_without_recipe_are_the_source_datasets_of_the_flow() -> None:
    project = FakeProject([], without_recipe=["input", "lookup"])

    assert read_datasets_without_recipe(project) == {"input", "lookup"}


def test_name_projects() -> None:
    assert name_projects(["A", "B"]) == "A, B"
    assert name_projects([]) == "other projects"
