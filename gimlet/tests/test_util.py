from unittest import TestCase

from gimlet.backends.sql import SQLBackend
from gimlet.util import asbool, parse_settings


class TestUtil(TestCase):

    def test_asbool_true(self):
        for val in ('T', 'trUe', 'y', 'yes', 'on', '1', True, 1):
            self.assertTrue(asbool(val))

    def test_asbool_false(self):
        for val in ('a', 'f', 'false', 'no', False, 0, None):
            self.assertFalse(asbool(val))

    def test_parse_settings(self):
        settings = {
            'gimlet.backend': 'sql',
            'gimlet.backend.url': 'sqlite:///:memory:',
            'gimlet.fake_https': True,
            'gimlet.secret': 'super-secret',
            'non-gimlet-setting': None,
        }
        options = parse_settings(settings)
        self.assertNotIn('non-gimlet-setting', options)

    def test_parse_settings_absolute_backend(self):
        settings = {
            'backend': 'gimlet.backends.sql',
            'backend.url': 'sqlite:///:memory:',
            'secret': 'super-secret',
        }
        options = parse_settings(settings, prefix='')
        self.assertIsInstance(options['backend'], SQLBackend)

    def test_parse_settings_None_backend(self):
        settings = {
            'backend': None,
            'secret': 'super-secret',
        }
        parse_settings(settings, prefix='')

    def test_parse_settings_bad_backend(self):
        settings = {
            'backend': object,
            'secret': 'super-secret',
        }
        self.assertRaises(ValueError, parse_settings, settings, prefix='')

    def test_parse_settings_unknown_backend(self):
        settings = {
            'backend': 'unknown_backend',
            'secret': 'super-secret',
        }
        self.assertRaises(ImportError, parse_settings, settings, prefix='')

    def test_parse_settings_no_secret(self):
        self.assertRaises(ValueError, parse_settings, {})
