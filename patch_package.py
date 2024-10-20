from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from __future__ import unicode_literals
from future import standard_library

standard_library.install_aliases()

import os
import subprocess
import site
import sys
from difflib import unified_diff, get_close_matches
from itertools import chain
import logging
import argparse
import collections

from pathlib2 import Path
from importlib_metadata import files, version, distributions, PackageNotFoundError
from backports.tempfile import TemporaryDirectory
import patch


def packages_distributions():
    pkg_to_dist = collections.defaultdict(list)
    for dist in distributions():
        for pkg in (dist.read_text("top_level.txt") or "").split():
            pkg_to_dist[pkg].append(dist.metadata["Name"])
    return dict(pkg_to_dist)


class PatchHandler(logging.StreamHandler):
    def emit(self, record):
        global last_log
        last_log = record.getMessage()


last_log = ""
logging.getLogger("patch").addHandler(PatchHandler())


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
        args = parser.parse_args(args)

        if args.package_name:
            try:
                package_version = version(args.package_name)
                print(
                    "Found installed version %s in current environment."
                    % package_version
                )
            except PackageNotFoundError:
                print("Package %s not found." % args.package_name)
                matches = match(args.package_name)
                if matches:
                    print("Did you mean %s ?" % " or ".join(matches))
                exit()

            package = "==".join((args.package_name, version(args.package_name)))
            print("Retrieving %s from PyPI..." % package)
            with open(os.devnull, "w") as DEVNULL:
                subprocess.check_call(
                    [
                        sys.executable,
                        "-m",
                        "pip",
                        "install",
                        package,
                        "--target",
                        temp_dir,
                        "--no-deps",
                        "--upgrade",
                    ],
                    stdout=DEVNULL,
                    stderr=DEVNULL,
                )

            print("Comparing files...")
            output = ""
            for file in files(args.package_name):
                if file.parent.suffix != ".dist-info" and file.suffix != ".pyc":
                    patched_lines = file.read_text().splitlines(True)
                    original_lines = (
                        (Path(temp_dir) / str(file)).read_text().splitlines(True)
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
                output_file.write_text(output)
                print("Done.")
            else:
                print("No changes detected. No patch created.")

        else:
            if not patch_dir.exists() or not any(patch_dir.iterdir()):
                print("No patches to apply. Exiting...")
                exit()
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

                patchset = patch.fromfile(str(patch_file))
                package_site = site.getsitepackages()[0]
                if not patchset.apply(root=package_site):
                    if "source file is different" in last_log:
                        source_file = last_log[29:-1]
                        print(
                            "Invalid patch for package %s because %s is different from the patch source."
                            % (package_name, Path(package_site) / source_file)
                        )
                        print("Please recreate or fix your patch. Skipping...")
                        continue
                else:
                    print("Patch applied successfully")


if __name__ == "__main__":
    main()
