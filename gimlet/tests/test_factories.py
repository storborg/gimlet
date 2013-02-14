from unittest import TestCase

from gimlet.factories import (
    session_factory_factory, session_factory_from_settings)
from gimlet.session import Session


class TestFactories(TestCase):

    def test_create_factory(self):
        factory = session_factory_factory('super-secret-awesome-sauce')
        self.assertTrue(issubclass(factory, Session))

    def test_create_factory_no_secret(self):
        self.assertRaises(TypeError, session_factory_factory)

    def test_create_factory_from_settings(self):
        factory = session_factory_from_settings(
            {'gimlet.secret': 'super-secret-awesome-sauce'})
        self.assertTrue(issubclass(factory, Session))
