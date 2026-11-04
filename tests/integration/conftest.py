"""Fixtures of the integration tests: a real DSS, its users, and a scratch project for each test.

The tests run only when the environment variable DSS_INTEGRATION_CONFIG gives the path of a config file.
Without it, they are skipped: `uv run pytest` and the CI never need a DSS. See docs/integration-tests.md.
"""

import json
import os
import subprocess
import sys
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from integration.dss import PLUGIN_ID, PROJECT_PREFIX

CONFIG_VARIABLE = "DSS_INTEGRATION_CONFIG"
ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def config() -> dict[str, Any]:
    """Return the config file: the URL of the DSS, the API keys, the owner of the scratch projects."""
    path = os.environ.get(CONFIG_VARIABLE)
    if not path:
        pytest.skip(f"Integration tests: set {CONFIG_VARIABLE} to the path of a config file.")
    pytest.importorskip("dataikuapi", reason="Integration tests: run them with `uv run --group integration`.")
    config: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    return config


def connect(config: dict[str, Any], role: str) -> Any:
    """Return a DSS client with the API key of this role, or skip the test when the config has none."""
    import dataikuapi

    key = (config.get("api_keys") or {}).get(role)
    if not key:
        pytest.skip(f"Integration tests: the config file has no API key for the {role}.")
    return dataikuapi.DSSClient(config["url"], key)


def install_plugin(client: Any, config: dict[str, Any]) -> None:
    """Install the plugin of this folder when the config asks for it, then check the version on the DSS."""
    version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
    if config.get("install_plugin"):
        subprocess.run([sys.executable, str(ROOT / "build_plugin_zip.py")], check=True, capture_output=True)
        with (ROOT / "dist" / f"dss-plugin-{PLUGIN_ID}-{version}.zip").open("rb") as archive:
            if PLUGIN_ID in {plugin["id"] for plugin in client.list_plugins()}:
                client.get_plugin(PLUGIN_ID).update_from_zip(archive)
            else:
                client.install_plugin_from_archive(archive)
    installed = {plugin["id"]: plugin.get("version") for plugin in client.list_plugins()}
    if installed.get(PLUGIN_ID) != version:
        pytest.fail(
            f"The DSS has the plugin {PLUGIN_ID} {installed.get(PLUGIN_ID)}, not {version}. "
            'Install the zip of this version, or set "install_plugin": true in the config file.'
        )


def check_not_admin(client: Any, role: str) -> None:
    """Fail when the user of this role is a DSS administrator: the tests of this role would prove nothing."""
    try:
        client.get_general_settings().get_raw()
    except Exception:
        return  # Only DSS administrators can read the general settings.
    pytest.fail(f"The {role} of the config file is a DSS administrator. Use the key of a simple user.")


@pytest.fixture(scope="session")
def admin(config: dict[str, Any]) -> Any:
    """Return the client of the DSS administrator. It creates and deletes the scratch projects."""
    client = connect(config, "admin")
    install_plugin(client, config)
    return client


@pytest.fixture(scope="session")
def editor(config: dict[str, Any], admin: Any) -> Any:
    """Return the client of a user who is not a DSS administrator. Each test gives them write access."""
    client = connect(config, "editor")
    check_not_admin(client, "editor")
    return client


@pytest.fixture(scope="session")
def reader(config: dict[str, Any], admin: Any) -> Any:
    """Return the client of a user who is not a DSS administrator. Each test gives them read access."""
    client = connect(config, "reader")
    check_not_admin(client, "reader")
    return client


@pytest.fixture(scope="session")
def connection(config: dict[str, Any]) -> str:
    """Return the connection of the managed datasets of the tests."""
    name: str = config.get("managed_connection", "filesystem_managed")
    return name


def delete_project(client: Any, project_key: str) -> None:
    """Delete a scratch project, with the data of its managed datasets."""
    assert project_key.startswith(PROJECT_PREFIX), f"{project_key} is not a scratch project."
    try:
        client.get_project(project_key).delete(clear_managed_datasets=True, clear_output_managed_folders=True)
    except Exception:
        pass  # DSS 13.4.4 answers the delete with an empty body, which the client cannot read.
    if project_key in client.list_project_keys():
        raise RuntimeError(f"The scratch project {project_key} could not be deleted.")


@pytest.fixture
def scratch_project(admin: Any, config: dict[str, Any]) -> Iterator[Any]:
    """Return a new, empty project for one test. It is deleted at the end, also when the test fails."""
    project_key = f"{PROJECT_PREFIX}{uuid.uuid4().hex[:8].upper()}"
    project = admin.create_project(project_key, f"{project_key} (integration test, scratch)", config["project_owner"])
    try:
        yield project
    finally:
        delete_project(admin, project_key)
