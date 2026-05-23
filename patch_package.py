from __future__ import absolute_import, division, print_function, unicode_literals

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

import whatthepatch

if sys.version_info < (3, 11):
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
                    "Found installed version %s in current environment."
                    % package_version
                )
            except PackageNotFoundError:
                print("Package %s not found." % parsed.package_name)
                matches = match(parsed.package_name)
                if matches:
                    raise Exception("Did you mean %s ?" % " or ".join(matches))

            package = "==".join((parsed.package_name, version(parsed.package_name)))
            print("Retrieving %s from PyPI..." % package)
            with open(os.devnull, "w") as DEVNULL:
                if shutil.which("uv"):
                    pip = ["uv", "pip"]
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
                if file.parent.suffix != ".dist-info" and file.suffix != ".pyc":
                    try:
                        patched_lines = file.read_text(encoding="utf-8").splitlines(
                            True
                        )
                    except UnicodeDecodeError:
                        print(
                            "Ignoring file %s because it is not UTF-8 encoded." % file
                        )
                        continue
                    original_lines = (
                        Path(temp_dir, file)
                        .read_text(encoding="utf-8")
                        .splitlines(True)
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
                        print("Changes detected in file %s." % file)
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
                print("Applying patch for package %s..." % package_name)
                try:
                    installed_version = version(package_name)
                except PackageNotFoundError:
                    print("Package %s not found. Skipping..." % package_name)
                    continue
                if package_version != installed_version:
                    print(
                        "Mismatching versions (%s and %s) %s not found. Skipping..."
                        % (installed_version, package_version, package_name)
                    )
                    continue

                package_site = sysconfig.get_path("purelib")
                for diff in whatthepatch.parse_patch(patch_file.read_text()):
                    target = Path(package_site, diff.header.new_path)
                    if not target.exists():
                        raise Exception(f"Patch target not found: {target}")
                    original = target.read_text(encoding="utf-8")
                    patched = whatthepatch.apply_diff(diff, original)
                    if patched[-1]:
                        patched.append("")
                    target.write_text("\n".join(patched), encoding="utf-8")


def cli():
    try:
        main()
    except Exception as e:
        print(e, file=sys.stderr)
        sys.exit(1)
