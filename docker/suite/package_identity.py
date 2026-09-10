"""Build the shared wheel once and refresh the four native dependency locks."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


def package(args):
    root = Path(__file__).resolve().parents[2]
    repos = {
        "drive": root,
        "st": args.st.resolve(),
        "people": args.people.resolve(),
        "docs": args.docs.resolve(),
    }
    # A reproducible wheel hash prevents lock churn when the source is unchanged.
    env = {**os.environ, "SOURCE_DATE_EPOCH": "1788825600"}
    with tempfile.TemporaryDirectory(prefix="suite-wheel-") as target:
        subprocess.run(
            [
                args.uv,
                "build",
                "--wheel",
                "--python",
                "3.13",
                "--out-dir",
                target,
                str(root / "src/packages/suite-identity"),
            ],
            check=True,
            env=env,
            stdout=subprocess.DEVNULL,
        )
        (wheel,) = Path(target).glob("*.whl")
        digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
        for app, repo in repos.items():
            backend = repo / "src/backend"
            vendor = backend / "vendor"
            vendor.mkdir(exist_ok=True)
            shutil.copy2(wheel, vendor / wheel.name)
            (vendor / "README.md").write_text(
                "# Shared suite identity package\n\n"
                "Generated from Apoze Drive `src/packages/suite-identity`.\n"
                "Refresh with Drive's `docker/suite/package_identity.py`; do not edit the wheel.\n"
                f"\nSHA-256: `{digest}`\n"
            )
            if app == "st":
                command = [
                    args.uv,
                    "tool",
                    "run",
                    "--python",
                    "3.13",
                    "--from",
                    "poetry==2.1.4",
                    "poetry",
                    "update",
                    "--lock",
                    "apoze-suite-identity",
                ]
            else:
                python = {"drive": "3.13", "people": "3.14.2", "docs": "3.14.6"}[app]
                command = [
                    args.uv,
                    "lock",
                    "--python",
                    python,
                    "--upgrade-package",
                    "apoze-suite-identity",
                ]
            subprocess.run(command, cwd=backend, check=True)
    print(f"Shared wheel and four locks refreshed; SHA-256 {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--st", type=Path, required=True)
    parser.add_argument("--people", type=Path, required=True)
    parser.add_argument("--docs", type=Path, required=True)
    package(parser.parse_args())
