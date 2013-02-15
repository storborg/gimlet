from unittest import TestCase

from webob import Request

from gimlet.factories import session_factory_factory


class TestSession(TestCase):

    def _make_session(self, secret='secret', **options):
        request = Request.blank('/')
        return session_factory_factory(secret, **options)(request)

    def test_session(self):
        sess = self._make_session()
        sess['a'] = 'a'
        self.assertIn('a', sess)
        self.assertIn('a', sess.channels['insecure'])

    def test_session_secure_nonperm(self):
        sess = self._make_session(secure=True, fake_https=True)
        sess['a'] = 'a'
        self.assertIn('a', sess.channels['secure_nonperm'])
        self.assertNotIn('a', sess.channels['insecure'])
        self.assertNotIn('a', sess.channels['secure_perm'])

    def test_session_secure_perm(self):
        sess = self._make_session(secure=True, permanent=True, fake_https=True)
        sess['a'] = 'a'
        self.assertIn('a', sess.channels['secure_perm'])
        self.assertNotIn('a', sess.channels['insecure'])
        self.assertNotIn('a', sess.channels['secure_nonperm'])

    def test_session_set_insecure(self):
        sess = self._make_session(secure=True, permanent=True, fake_https=True)
        sess.set('a', 'a', secure=False)
        self.assertIn('a', sess.channels['insecure'])
        self.assertNotIn('a', sess.channels['secure_perm'])
        self.assertNotIn('a', sess.channels['secure_nonperm'])

    def test_invalidate(self):
        sess = self._make_session()
        sess['a'] = 'a'
        self.assertIn('a', sess)
        sess.invalidate()
        self.assertNotIn('a', sess)

    def test_csrf(self):
        sess = self._make_session()
        self.assertNotIn('_csrft_', sess)
        token = sess.get_csrf_token()
        self.assertIn('_csrft_', sess)
        self.assertEqual(token, sess.get_csrf_token())
