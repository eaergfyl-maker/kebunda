"""Route discovery.

Each sub-folder (farms/, nasa/, soil-crops/, rotations/, scenarios/) holds a `router.py`
exposing `router`. Folders are loaded by path, so a hyphenated folder name is fine and a
new route group needs no registration: add a folder with a router.py and it is mounted.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

from fastapi import APIRouter


def load_routers() -> list[APIRouter]:
    routers = []
    for path in sorted(Path(__file__).parent.glob("*/router.py")):
        name = "app.api.routes." + path.parent.name.replace("-", "_") + ".router"
        spec = importlib.util.spec_from_file_location(name, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        routers.append(module.router)
    return routers
