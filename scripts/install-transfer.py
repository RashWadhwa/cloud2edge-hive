#!/usr/bin/env python3
"""Entry point embedded in the downloadable EdgeClimate ZIP (Python stdlib only)."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import sys
import tempfile
import zipfile


def digest(data):
    return hashlib.sha256(data).hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ("..", ".git", ".edge") for p in path.parts):
        raise ValueError("Unsafe archive path")
    if str(path) != name or "\\" in name:
        raise ValueError("Noncanonical archive path")
    if name not in ("README.md", ".gitignore", "compose.edge.yml") and path.parts[0] not in ("edge", "scripts", "docs"):
        raise ValueError("Unexpected archive path: " + name)
    return path


def atomic_write(path, data, mode):
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".edge-transfer-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def install(archive, target, backup_root, dry_run=False):
    target = target.expanduser().resolve()
    if not target.is_dir() or not (target / ".git").exists():
        raise ValueError("Target must be your existing Git checkout, e.g. ~/cloud2edge-hive")
    backup_root = backup_root.expanduser().resolve()
    if backup_root.is_relative_to(target):
        raise ValueError("Backup directory must be outside the checkout")
    plans = []
    # Verify every payload before touching any destination.
    with zipfile.ZipFile(archive) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        if manifest.get("format") != 1 or not manifest.get("files"):
            raise ValueError("Invalid bundle manifest")
        for name, metadata in manifest["files"].items():
            relative = safe_name(name)
            data = bundle.read("payload/" + name)
            if digest(data) != metadata["sha256"]:
                raise ValueError("Checksum mismatch: " + name)
            destination = target.joinpath(*relative.parts)
            if destination.is_symlink() or not destination.resolve().is_relative_to(target):
                raise ValueError("Destination symlink escapes or replaces an existing link: " + name)
            # A symlinked parent is rejected even when it currently resolves inside.
            parent = destination.parent
            while parent != target:
                if parent.is_symlink():
                    raise ValueError("Symlinked destination directory: " + name)
                parent = parent.parent
            if destination.exists() and not destination.is_file():
                raise ValueError("Destination is not a regular file: " + name)
            original = destination.read_bytes() if destination.exists() else None
            if name == ".gitignore" and original is not None:
                # Merge only our runtime exclusion, preserving all local rules.
                if b"/.edge/" not in original.splitlines() and b".edge/" not in original.splitlines():
                    data = original + (b"\n" if not original.endswith(b"\n") else b"") + b"\n# EdgeClimate private runtime\n/.edge/\n"
                else:
                    data = original
            if original == data:
                continue
            mode = 0o755 if metadata.get("executable") else 0o644
            plans.append((name, destination, data, mode, original))
    if dry_run:
        for name, _, _, _, original in plans:
            print(("REPLACE (backed up): " if original is not None else "ADD: ") + name)
        print(f"Verified bundle; {len(plans)} files would change. Nothing copied.")
        return
    if not plans:
        print("Already installed: all project files match. Local settings and data preserved.")
        return
    backup_root.mkdir(parents=True, mode=0o700, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-"), dir=backup_root))
    written = []
    try:
        # Back up every replaced file and check the backup before any replacement.
        for name, destination, _, _, original in plans:
            if original is not None:
                saved = backup / name
                saved.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(destination, saved)
                if saved.read_bytes() != original:
                    raise ValueError("Source changed while backing up: " + name)
        for name, destination, data, mode, original in plans:
            current = destination.read_bytes() if destination.exists() else None
            if current != original:
                raise ValueError("Destination changed during transfer: " + name)
            atomic_write(destination, data, mode)
            written.append((name, destination, original))
        receipt = {"installed_at_utc": datetime.now(timezone.utc).isoformat(), "target": str(target),
                   "files": [{"path": name, "installed_sha256": digest(data),
                              "previous_sha256": digest(original) if original is not None else None}
                             for name, _, data, _, original in plans]}
        (backup / "transfer-receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    except Exception:
        for name, destination, original in reversed(written):
            if original is None:
                destination.unlink()
            else:
                saved = backup / name
                atomic_write(destination, saved.read_bytes(), saved.stat().st_mode & 0o777)
        print("Transfer failed; copied files rolled back. Backup:", backup, file=sys.stderr)
        raise
    print(f"Installed {len(plans)} project files into {target}")
    print("Replaced source files backed up at:", backup)
    print("Preserved .env, .edge, existing container data, Git history and unrelated files.")
    print("No credentials transferred, Git commands run, firmware flashed or services started.")
    print("Next: cd", target)
    print("      ./scripts/edge init")
    print("Then follow docs/PROJECT.md to configure the Arduino and dashboard access.")


def main():
    parser = argparse.ArgumentParser(description="Transfer verified EdgeClimate source files into your Pi checkout.")
    parser.add_argument("--target", type=Path, default=Path.home() / "cloud2edge-hive")
    parser.add_argument("--backup-dir", type=Path, default=Path.home() / "edgeclimate-transfer-backups")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    install(Path(sys.argv[0]).resolve(), args.target, args.backup_dir, args.dry_run)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, zipfile.BadZipFile) as error:
        raise SystemExit("Transfer stopped: " + str(error)) from None
