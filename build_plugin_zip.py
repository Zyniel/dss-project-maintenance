"""Build the zip to upload in DSS: Plugins > Add plugin > Upload."""

import json
import zipfile
from pathlib import Path

# The paths are relative to this file, so that the script works from any folder.
ROOT = Path(__file__).resolve().parent

version = json.loads((ROOT / "plugin.json").read_text(encoding="utf-8"))["version"]
zip_path = ROOT / "dist" / f"dss-plugin-project-maintenance-{version}.zip"
zip_path.parent.mkdir(exist_ok=True)

with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as plugin_zip:
    plugin_zip.write(ROOT / "plugin.json", "plugin.json")
    plugin_zip.write(ROOT / "README.md", "README.md")
    for folder in ["python-lib", "python-runnables", "resource"]:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts:
                plugin_zip.write(path, path.relative_to(ROOT).as_posix())

print(zip_path)
