import unittest

import neomapper
from neomapper.shared.version import APP_TITLE, APP_VERSION


class VersionTests(unittest.TestCase):
    def test_package_and_application_versions_match(self):
        self.assertEqual(neomapper.__version__, APP_VERSION)
        self.assertEqual(APP_VERSION, "4.2.3")
        self.assertEqual(APP_TITLE, "NEOMapper")
