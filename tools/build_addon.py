"""Builds minecRAFT-bedrock.mctemplate from the repository, so nothing is copied into a zip by hand.

The archive is what Minecraft imports when the file is double-clicked: the world template's own files at the
root (world/: manifest.json, level.dat, levelname.txt, world_icon.jpeg; no db/, so the game generates the ocean
when the world is created), and the packs under behavior_packs/ and resource_packs/, each with its manifest.json
directly inside. The packs are this repository's behavior and resource packs and both packs of the Display add-on
(https://github.com/kirbycope/display-bedrock), read from a checkout of that repository, by default the one
beside this one in C:\\GitHub. The pack lists, world_behavior_packs.json and world_resource_packs.json, are
written from the packs' manifests, so bumping a manifest version is enough.

    python tools/build_addon.py                         # writes build/minecRAFT-bedrock.mctemplate
    python tools/build_addon.py --display path/to/it    # takes the Display packs from another checkout
    python tools/build_addon.py --check                 # exits 1 if the archive on disk differs from a fresh build

What Minecraft requires of the zip: entries at the root (no wrapping folder), forward slashes in entry names,
Deflate or Store, no zip64. Images and sounds, already compressed, are stored rather than deflated.
"""

import argparse
import io
import json
import os
import subprocess
import sys
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORLD = os.path.join(ROOT, "world")
DISPLAY = os.path.join(os.path.dirname(ROOT), "display-bedrock")
OUTPUT = os.path.join(ROOT, "build", "minecRAFT-bedrock.mctemplate")
LISTS = {"behavior_packs": "world_behavior_packs.json", "resource_packs": "world_resource_packs.json"}
STAMP = (2026, 1, 1, 0, 0, 0)   # a fixed timestamp keeps the archive byte-for-byte reproducible, so --check can compare it
STORED = {".png", ".jpg", ".jpeg", ".ogg", ".fsb"}
LIMIT = 100 * 1024 * 1024   # GitHub refuses a file over 100 MB


def packs(display: str) -> dict[str, tuple[str, str]]:
    """Folder in the archive -> (repository, pack folder inside it)."""
    return {
        "behavior_packs/minecraft_raft": (ROOT, "development_behavior_packs/minecraft_raft"),
        "resource_packs/minecraft_raft": (ROOT, "development_resource_packs/minecraft_raft"),
        "behavior_packs/Display": (display, "development_behavior_packs/Display"),
        "resource_packs/Display": (display, "development_resource_packs/Display"),
    }


def tracked(repo: str, pack: str) -> list[str]:
    """The files git tracks under a pack, as paths relative to it, sorted, those deleted from the working tree left out."""
    out = subprocess.run(["git", "-C", repo, "ls-files", "-z", "--", pack], check=True, capture_output=True).stdout.decode("utf-8")
    return sorted(p[len(pack) + 1:] for p in out.split("\0") if p and os.path.isfile(os.path.join(repo, p)))


def pack_list(kind: str, display: str) -> bytes:
    """The world's list of packs of one kind, written from their manifests."""
    entries = []
    for folder, (repo, pack) in packs(display).items():
        if folder.split("/")[0] == kind:
            with open(os.path.join(repo, pack, "manifest.json"), encoding="utf-8-sig") as handle:
                header = json.load(handle)["header"]
            entries.append({"pack_id": header["uuid"], "version": header["version"]})
    return (json.dumps(entries, indent="\t") + "\n").encode("utf-8")


def build(display: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED, allowZip64=False) as archive:
        seen: set[str] = set()

        def add_dir(path: str) -> None:
            parts = path.split("/")
            for depth in range(1, len(parts)):
                folder = "/".join(parts[:depth]) + "/"
                if folder in seen: continue
                seen.add(folder)
                info = zipfile.ZipInfo(folder, STAMP)
                info.external_attr = 0o40777 << 16
                archive.writestr(info, b"", zipfile.ZIP_STORED)

        def add(path: str, data: bytes) -> None:
            add_dir(path)
            info = zipfile.ZipInfo(path, STAMP)
            info.external_attr = 0o666 << 16
            info.compress_type = zipfile.ZIP_STORED if os.path.splitext(path)[1].lower() in STORED else zipfile.ZIP_DEFLATED
            archive.writestr(info, data, compresslevel=9)

        for relative in tracked(ROOT, "world"):
            with open(os.path.join(WORLD, relative), "rb") as handle:
                add(relative, handle.read())
        for kind, name in LISTS.items():
            add(name, pack_list(kind, display))
        for folder, (repo, pack) in packs(display).items():
            for relative in tracked(repo, pack):
                with open(os.path.join(repo, pack, relative), "rb") as handle:
                    add(f"{folder}/{relative}", handle.read())
    return buffer.getvalue()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="report whether the archive is up to date instead of writing it")
    parser.add_argument("--display", default=DISPLAY, help="a checkout of kirbycope/display-bedrock")
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()

    data = build(os.path.abspath(args.display))
    if len(data) > LIMIT:
        print(f"refusing to write {len(data)} bytes, over GitHub's 100 MB limit", file=sys.stderr)
        return 1
    current = os.path.exists(args.output) and open(args.output, "rb").read() == data
    if args.check:
        print("up to date" if current else f"out of date: {os.path.relpath(args.output, ROOT)}")
        return 0 if current else 1
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "wb") as handle:
        handle.write(data)
    print(f"wrote {os.path.relpath(args.output, ROOT)} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
