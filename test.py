#type: ignore
from __future__ import division
from __future__ import print_function
from __future__ import absolute_import
from __future__ import unicode_literals
from future import standard_library

standard_library.install_aliases()

import unittest
import sys
import subprocess
import site

if sys.version_info < (3,):
    from pathlib2 import Path
else:
    from pathlib import Path

from patch_package import main, match

test_package = 'requests'
package_site = Path(site.getsitepackages()[0])
test_file = (package_site / "requests" / "__version__.py")

class PatchTest(unittest.TestCase):
    def test_patch(self):
        subprocess.check_call([sys.executable, "-m", "pip", "install", test_package])
        with test_file.open('r') as f:
            original_lines = f.readlines()
        modified_lines = original_lines[:]
        modified_lines[5] = "MOUHAHAHA\n"
        with test_file.open('w') as f:
            f.writelines(modified_lines)
        main([test_package])
        subprocess.check_call([sys.executable, "-m", "pip", "install", "--force-reinstall", test_package])
        self.assertEqual(test_file.read_text(), ''.join(original_lines))
        main()
        self.assertEqual(test_file.read_text(), ''.join(modified_lines))

    def test_pkg_match(self):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "jaraco.classes"])
        matches = match('jaraco')
        self.assertIn('jaraco.classes', matches)

    def test_dist_match(self):
        subprocess.check_call([sys.executable, "-m", "pip", "install", "jaraco.classes"])
        self.assertEqual(match('classes'), ['jaraco.classes'])

    def test_fuzzy_match(self):
        self.assertEqual(match('post'), ['future'])

    def tearDown(self):
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", test_package])
        subprocess.check_call([sys.executable, "-m", "pip", "uninstall", "-y", "jaraco.classes"])
        pth = Path('patches')
        if pth.exists():
            for child in pth.iterdir():
                child.unlink()
            pth.rmdir()


if __name__ == '__main__':
    unittest.main()
