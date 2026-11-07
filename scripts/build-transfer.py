#!/usr/bin/env python3
"""Build a source-only, executable ZIP for transfer without GitHub credentials."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def build(output):
    listing = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z", "--",
         "README.md", ".gitignore", "compose.edge.yml", "edge", "scripts", "docs"],
        check=True, cwd=ROOT, capture_output=True).stdout
    names = sorted(set(n.decode() for n in listing.split(b"\0") if n))
    manifest = {"format": 1, "title": "EdgeClimate Pi source transfer", "files": {}}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for name in names:
            source = ROOT / name
            if source.is_symlink() or not source.resolve().is_relative_to(ROOT):
                raise ValueError("Source is a symlink or escapes the checkout: " + name)
            data = source.read_bytes()
            manifest["files"][name] = {"sha256": hashlib.sha256(data).hexdigest(),
                                       "executable": bool(source.stat().st_mode & 0o111)}
            bundle.writestr("payload/" + name, data)
        bundle.writestr("manifest.json", json.dumps(manifest, indent=2) + "\n")
        bundle.writestr("__main__.py", (ROOT / "scripts/install-transfer.py").read_bytes())
    print(f"Built {output}: {len(names)} source files, {output.stat().st_size} bytes")
    print("SHA256:", hashlib.sha256(output.read_bytes()).hexdigest())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    build(parser.parse_args().output)
