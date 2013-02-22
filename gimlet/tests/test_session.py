from unittest import TestCase

from webob import Request, Response

from webtest import TestApp

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


class App(object):

    def __init__(self):
        self.session_factory = session_factory_factory('secret')

    def __call__(self, environ, start_response):
        request = Request(environ)
        request.session = self.session_factory(request)
        view_name = request.path_info_pop()
        view = getattr(self, view_name)
        response = view(request)
        request.session.response_callback(request, response)
        return response(environ, start_response)

    def get(self, request):
        return Response('get')

    def set(self, request):
        request.session['a'] = 'a'
        return Response('set')

    def invalidate(self, request):
        request.session.invalidate()
        return Response('invalidate')


class TestSession_Functional(TestCase):

    def setUp(self):
        self.app = TestApp(App())

    def test_invalidate(self):
        # First request has no cookies; this sets them
        res = self.app.get('/set')
        self.assertEqual(res.request.cookies, {})
        self.assertIn('Set-Cookie', res.headers)
        # Next request should contain cookies
        res = self.app.get('/get')
        self.assert_(res.request.cookies)
        self.assertIn('gimlet', res.request.cookies)
        old_cookie_value = res.request.cookies['gimlet']
        self.assert_(old_cookie_value)
        # Invalidation should empty the session and set a new cookie
        res = self.app.get('/invalidate')
        self.assertIn('Set-Cookie', res.headers)
        self.assertEqual(res.request.session, {})
        res = self.app.get('/get')
        self.assertIn('gimlet', res.request.cookies)
        new_cookie_value = res.request.cookies['gimlet']
        self.assert_(new_cookie_value)
        self.assertNotEqual(new_cookie_value, old_cookie_value)
