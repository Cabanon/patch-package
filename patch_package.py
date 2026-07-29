import argparse
import os
import shutil
import subprocess
import sys
import sysconfig
from difflib import get_close_matches, unified_diff
from itertools import chain
from pathlib import Path
from tempfile import TemporaryDirectory

from unidiff import PatchSet

if sys.version_info < (3, 10):
    from importlib_metadata import (
        PackageNotFoundError,
        files,
        packages_distributions,
        version,
    )
else:
    from importlib.metadata import (
        PackageNotFoundError,
        files,
        packages_distributions,
        version,
    )


def match(name):
    dists = packages_distributions()
    if name in dists:
        return dists[name]
    matches = get_close_matches(name, chain(*dists.values()))
    if matches:
        return matches
    pkg_matches = get_close_matches(name, dists.keys(), 1)
    if pkg_matches:
        return dists[pkg_matches[0]]


def main(args=None):
    with TemporaryDirectory() as temp_dir:
        patch_dir = Path("patches")

        parser = argparse.ArgumentParser(
            description="A tool to create and apply patches to python packages."
        )
        parser.add_argument(
            "package_name",
            nargs="?",
            help="The name of the package to create a patch for",
        )
        parsed = parser.parse_args(args)

        if parsed.package_name:
            try:
                package_version = version(parsed.package_name)
                print(
                    f"Found installed version {package_version} in current environment."
                )
            except PackageNotFoundError:
                print(f"Package {parsed.package_name} not found.")
                matches = match(parsed.package_name)
                if matches:
                    raise Exception(f"Did you mean {' or '.join(matches)} ?")

            package = "==".join((parsed.package_name, version(parsed.package_name)))
            print(f"Retrieving {package} from PyPI...")
            with open(os.devnull, "w") as DEVNULL:
                if shutil.which("uv"):
                    pip = ["uv", "tool", "run", "pip"]
                else:
                    subprocess.check_call([sys.executable, "-m", "ensurepip"])
                    pip = [sys.executable, "-m", "pip"]
                subprocess.check_call(
                    [
                        *pip,
                        "install",
                        package,
                        "--target",
                        temp_dir,
                        "--no-deps",
                        "--no-cache",
                    ],
                    stdout=DEVNULL,
                    stderr=DEVNULL,
                )

            print("Comparing files...")
            output = ""
            for file in files(parsed.package_name):
                if file.suffix != ".py":
                    continue
                try:
                    patched_lines = file.read_text(encoding="utf-8").splitlines(True)
                except UnicodeDecodeError:
                    print(f"Ignoring file {file} because it is not UTF-8 encoded.")
                    continue
                original_lines = (
                    Path(temp_dir, file).read_text(encoding="utf-8").splitlines(True)
                )
                diff = list(
                    unified_diff(
                        original_lines,
                        patched_lines,
                        fromfile=str(file),
                        tofile=str(file),
                    )
                )
                if diff:
                    print(f"Changes detected in file {file}.")
                    output += "".join(diff)

            if output:
                print("Writing patch file...")
                patch_dir.mkdir(exist_ok=True)
                output_file = patch_dir / (package + ".patch")
                if output_file.exists():
                    print(
                        "Patch file already exists, would you like to overwrite it ? (y/n)"
                    )
                    if input().lower() != "y":
                        raise Exception("Aborted")
                output_file.write_text(output)
                print("Done.")
            else:
                print("No changes detected. No patch created.")
        else:
            if not patch_dir.exists() or not any(patch_dir.iterdir()):
                raise Exception("No patches to apply. Exiting...")
            for patch_file in patch_dir.glob("*.patch"):
                package_name, package_version = patch_file.stem.split("==")
                print(f"Applying patch for package {package_name}...")
                try:
                    installed_version = version(package_name)
                except PackageNotFoundError:
                    print(f"Package {package_name} not found. Skipping...")
                    continue
                if package_version != installed_version:
                    print(
                        f"Mismatching versions ({installed_version} and {package_version}) for package {package_name}. Skipping..."
                    )
                    continue

                package_site = sysconfig.get_path("purelib")
                for patch in PatchSet(patch_file.read_text()):
                    target = Path(package_site, patch.source_file)
                    if not target.exists():
                        raise Exception(f"Patch target not found: {target}")
                    lines = target.read_text(encoding="utf-8").splitlines(True)
                    offset = 0
                    for hunk in patch:
                        i = hunk.source_start - 1 + offset
                        for line in hunk:
                            if line.is_context:
                                if i < len(lines) and lines[i] == line.value:
                                    i += 1
                                else:
                                    raise Exception(
                                        f"Context mismatch at {target}:{i + 1}\n"
                                        f"Expected: {line.value!r}\n"
                                        f"Found:    {lines[i]!r}"
                                    )
                            elif line.is_removed:
                                if i < len(lines) and lines[i] == line.value:
                                    del lines[i]
                                    offset -= 1
                            elif line.is_added:
                                if i < len(lines) and lines[i] == line.value:
                                    i += 1
                                else:
                                    lines.insert(i, line.value)
                                    i += 1
                                    offset += 1
                    target.write_text("".join(lines), encoding="utf-8")


def cli():
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
