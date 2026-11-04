"""Run the integration in a real Home Assistant container against the Govee cloud.

Needs Docker and a Govee account:

    GOVEE_EMAIL=you@example.com GOVEE_PASSWORD=... python scripts/smoke_test.py

Options:
    --ha-version 2026.11.0   Home Assistant image tag (default: stable)
    --config-dir DIR         Reuse a config dir between runs (e.g. to test upgrades);
                             by default a temporary one is created and removed.
    --component DIR          Integration folder to mount (default: this repo's).

Prints the state of every govee_cloud entity plus any warnings Home Assistant
logged about the integration. Exits non-zero if the integration did not load.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

REPO = Path(__file__).resolve().parent.parent
CONTAINER = "govee-cloud-smoke-test"
FAILURE_MARKERS = (
    "Setup failed for custom integration govee_cloud",
    "for govee_cloud integration not ready yet",
    "for govee_cloud integration could not authenticate",
    "Error setting up entry",
)


def setup_outcome(logs: str) -> str | None:
    """Return "ok" or "failed" once the first refresh is logged, else None.

    The coordinator logs "Finished fetching govee_cloud data ... (success: X)" for
    failed refreshes too, so only success: True counts as loaded.
    """
    for line in logs.splitlines():
        if "Finished fetching govee_cloud data" in line:
            return "ok" if "(success: True)" in line else "failed"
        if any(marker in line for marker in FAILURE_MARKERS):
            return "failed"
    return None

STATES_SCRIPT = r"""
import json, os, sqlite3

def storage(name, key):
    path = f'/config/.storage/{name}'
    return json.load(open(path))['data'][key] if os.path.exists(path) else []

entities = storage('core.entity_registry', 'entities')
ids = sorted(e['entity_id'] for e in entities if e['platform'] == 'govee_cloud')
disabled = {e['entity_id'] for e in entities if e['platform'] == 'govee_cloud' and e['disabled_by']}
for device in storage('core.device_registry', 'devices'):
    if any(identifier[0] == 'govee_cloud' for identifier in device['identifiers']):
        print(f"device: {device['name']} ({device['model']}), entry_type={device['entry_type']}")
for entry in storage('core.config_entries', 'entries'):
    if entry['domain'] == 'govee_cloud':
        print(f"config entry: version {entry['version']}.{entry.get('minor_version')}, unique_id={entry.get('unique_id')}")
states = {}
if os.path.exists('/config/home-assistant_v2.db'):
    db = sqlite3.connect('file:/config/home-assistant_v2.db?mode=ro', uri=True)
    query = '''select m.entity_id, s.state, a.shared_attrs from states s
      join states_meta m on s.metadata_id = m.metadata_id
      left join state_attributes a on s.attributes_id = a.attributes_id
      where s.state_id in (select max(state_id) from states group by metadata_id)'''
    states = {row[0]: (row[1], json.loads(row[2] or '{}')) for row in db.execute(query)}
for entity_id in ids:
    if entity_id in disabled:
        print(f"{entity_id:45} (disabled)")
        continue
    state, attrs = states.get(entity_id, ('<no state>', {}))
    print(f"{entity_id:45} {state:>12} {attrs.get('unit_of_measurement') or ''}")
"""


def docker(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["docker", *args], check=check, capture_output=True, text=True, encoding="utf-8", errors="replace"
    )


def prepare_config(config_dir: Path, email: str, password: str) -> None:
    storage = config_dir / ".storage"
    storage.mkdir(parents=True, exist_ok=True)
    configuration = config_dir / "configuration.yaml"
    if not configuration.exists():
        configuration.write_text(
            "homeassistant:\n  name: Smoke test\n  unit_system: metric\n"
            "recorder:\n  commit_interval: 1\n"
            "logger:\n  default: warning\n  logs:\n    custom_components.govee_cloud: debug\n",
            encoding="utf-8",
        )
    entries = storage / "core.config_entries"
    if not entries.exists():
        entries.write_text(
            json.dumps(
                {
                    "version": 1,
                    "minor_version": 1,
                    "key": "core.config_entries",
                    "data": {
                        "entries": [
                            {
                                "entry_id": "0123456789abcdef0123456789abcdef",
                                "version": 1,
                                "minor_version": 2,
                                "domain": "govee_cloud",
                                "title": f"Govee Cloud ({email})",
                                "data": {"email": email, "password": password},
                                "options": {},
                                "pref_disable_new_entities": False,
                                "pref_disable_polling": False,
                                "source": "user",
                                "unique_id": email.strip().lower(),
                                "disabled_by": None,
                            }
                        ]
                    },
                }
            ),
            encoding="utf-8",
        )


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ha-version", default="stable")
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--component", type=Path, default=REPO / "custom_components" / "govee_cloud")
    parser.add_argument("--timeout", type=int, default=240)
    args = parser.parse_args()

    email, password = os.environ.get("GOVEE_EMAIL"), os.environ.get("GOVEE_PASSWORD")
    if not email or not password:
        print("Set GOVEE_EMAIL and GOVEE_PASSWORD", file=sys.stderr)
        return 2

    temporary = args.config_dir is None
    config_dir = Path(tempfile.mkdtemp(prefix="govee-smoke-")) if temporary else args.config_dir.resolve()
    prepare_config(config_dir, email, password)

    image = f"ghcr.io/home-assistant/home-assistant:{args.ha_version}"
    docker("rm", "-f", CONTAINER, check=False)
    started = time.time()
    try:
        docker(
            "run", "-d", "--name", CONTAINER,
            "-v", f"{config_dir}:/config",
            "-v", f"{args.component.resolve()}:/config/custom_components/govee_cloud:ro",
            image,
        )
        version = docker("exec", CONTAINER, "python3", "-c",
                         "from homeassistant.const import __version__; print(__version__)").stdout.strip()
        print(f"Home Assistant {version}")

        outcome = None
        while time.time() - started < args.timeout:
            result = docker("logs", CONTAINER, check=False)
            outcome = setup_outcome(result.stdout + result.stderr)
            if outcome:
                break
            time.sleep(3)
        else:
            print("Timed out waiting for the integration to load", file=sys.stderr)
        if outcome == "ok":
            time.sleep(10)  # let the first states reach the recorder

        # A graceful stop makes Home Assistant write its registries to disk.
        docker("stop", "--time", "60", CONTAINER, check=False)
        result = docker("logs", CONTAINER, check=False)
        logs = result.stdout + result.stderr
        states = docker(
            "run", "--rm", "-v", f"{config_dir}:/config", "--entrypoint", "python3",
            image, "-c", STATES_SCRIPT, check=False,
        )
        print(states.stdout)
        if states.returncode != 0:
            print(f"Reading states failed:\n{states.stderr}", file=sys.stderr)
        problems = sorted(
            {
                line.strip()
                for line in logs.splitlines()
                if "govee_cloud" in line
                and ("WARNING" in line or "ERROR" in line)
                and "has not been tested by Home Assistant" not in line
            }
        )
        print("Warnings/errors about govee_cloud:" if problems else "No warnings or errors about govee_cloud.")
        for line in problems:
            print("  " + line)
        if outcome != "ok":
            print("FAILED: the integration did not load", file=sys.stderr)
            return 1
        return 1 if states.returncode != 0 else 0
    finally:
        docker("rm", "-f", CONTAINER, check=False)
        if temporary:
            shutil.rmtree(config_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
