"""A minimal FastAPI server exposing KIKX's real /service/micro/* routes,
backed by the real asyncio Micro/MicroServices classes from a local KIKX
checkout, against a real installed copy of the given .kikx package.

Only the HTTP auth layer is replaced -- the get_app dependency is overridden
to hand back a directly constructed App object -- so this is the actual KIKX
micro service implementation running over real HTTP, not a reimplementation.

Usage: real-micro-server.py <kikx-source-path> <package.kikx> <port>
"""
import shutil
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

kikx_source, package_path, port = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
sys.path.insert(0, str(Path(kikx_source) / "kikx"))

from fastapi import FastAPI
from core.app import App
from core.kpm import AppInstaller
from core.setup.pkg import extract_package
from core.models.app import AppManifestModel, AppModel
from lib.parser import parse_config

import services.micro.main as micro_module

root = Path(tempfile.mkdtemp())
apps_path, apps_data_path = root / "apps", root / "apps-data"
storage_path, home_path, data_path = root / "storage", root / "home", root / "data"

for path in (root, apps_path, apps_data_path, storage_path, home_path, data_path):
  path.mkdir(parents=True, exist_ok=True)
  path.chmod(0o755)

core_stub = SimpleNamespace(
  version="0.4.0",
  config=SimpleNamespace(apps_path=apps_path, apps_data_path=apps_data_path),
)

temp_dir = Path(tempfile.mkdtemp())
raw = temp_dir / package_path.name
shutil.copy(package_path, raw)
extract_dir = temp_dir / "extracted"
extract_dir.mkdir()
extracted_path = extract_package(raw, extract_dir)

installer = AppInstaller(core_stub, extracted_path)
installer.install("local")
app_name = installer.app_name
app_path = apps_path / app_name

app_config = parse_config(apps_data_path / f"{app_name}.json", AppModel)
manifest = parse_config(app_path / "app.json", AppManifestModel)

user = SimpleNamespace(
  storage_path=storage_path,
  home_path=home_path,
  data_path=data_path,
  save_app_config=lambda name, cfg: None,
)

real_app = App("test-client", app_name, app_path, app_config, user, manifest, {})

fastapi_app = FastAPI()
fastapi_app.include_router(micro_module.srv.router, prefix="/service/micro")
fastapi_app.dependency_overrides[micro_module.get_app] = lambda: real_app

if __name__ == "__main__":
  import uvicorn

  print("ready", flush=True)
  uvicorn.run(fastapi_app, host="127.0.0.1", port=port, log_level="warning")
