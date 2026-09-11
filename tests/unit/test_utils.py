import unittest

from neomapper.shared.utils import (
    minutes_from_duration,
    minutes_from_step_label,
    safe_filename,
)


class FilenameTests(unittest.TestCase):
    def test_sanitizes_object_designation(self):
        self.assertEqual(safe_filename("(99942) Apophis / test"), "99942_Apophis_-_test")

    def test_empty_filename_uses_object(self):
        self.assertEqual(safe_filename(""), "object")


class DurationTests(unittest.TestCase):
    def test_parses_localized_step_labels(self):
        self.assertEqual(minutes_from_step_label("2 horas"), 120)
        self.assertEqual(minutes_from_step_label("1 day"), 1440)
        self.assertEqual(minutes_from_step_label("15 minutes"), 15)

    def test_converts_duration_units(self):
        self.assertEqual(minutes_from_duration("1.5", "hours"), 90)
        self.assertEqual(minutes_from_duration("2", "dias"), 2880)
        self.assertEqual(minutes_from_duration("0", "minutes"), 1)
