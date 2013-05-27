from unittest import TestCase

from webob import Request, Response

import webtest

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

    def test_flash(self):
        sess = self._make_session()
        self.assertEqual(sess.peek_flash(), [])
        sess.flash('abc')
        sess.flash('abc')
        self.assertEqual(sess.peek_flash(), ['abc', 'abc'])
        self.assertEqual(sess.pop_flash(), ['abc', 'abc'])
        self.assertEqual(sess.peek_flash(), [])
        sess.flash('xyz', allow_duplicate=False)
        sess.flash('xyz', allow_duplicate=False)
        self.assertEqual(sess.peek_flash(), ['xyz'])

    def test_csrf(self):
        sess = self._make_session()
        self.assertNotIn('_csrft_', sess)
        token = sess.get_csrf_token()
        self.assertIn('_csrft_', sess)
        self.assertEqual(token, sess.get_csrf_token())


class TestRequest(webtest.TestRequest):

    @property
    def session(self):
        return self.environ['gimlet.session']


class TestApp(webtest.TestApp):

    RequestClass = TestRequest


class App(object):

    def __init__(self):
        self.session_factory = session_factory_factory('secret')

    def __call__(self, environ, start_response):
        request = TestRequest(environ)
        environ['gimlet.session'] = self.session_factory(request)
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

    def mutate_set(self, request):
        request.session['b'] = {'bar': 42}
        return Response('mutate_set')

    def mutate_get(self, request):
        s = ','.join(['%s:%s' % (k, v)
                      for k, v in sorted(request.session['b'].items())])
        return Response(s)

    def mutate_nosave(self, request):
        request.session['b']['foo'] = 123
        return Response('mutate_nosave')

    def mutate_save(self, request):
        request.session['b']['foo'] = 123
        request.session.save()
        return Response('mutate_save')

    def mangle_cookie(self, request):
        resp = Response('mangle_cookie')
        resp.set_cookie('gimlet', request.cookies['gimlet'].lower())
        return resp


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

    def test_bad_signature(self):
        # First request has no cookies; this sets them
        res = self.app.get('/set')
        self.assertEqual(res.request.cookies, {})
        self.assertIn('Set-Cookie', res.headers)
        # Mangle cookie
        orig_cookie = self.app.cookies['gimlet']
        self.app.get('/mangle_cookie')
        mangled_cookie = self.app.cookies['gimlet']
        self.assertEqual(mangled_cookie, orig_cookie.lower())
        # Next request should succeed and then set a new cookie
        self.app.get('/get')
        self.assertIn('gimlet', self.app.cookies)
        self.assertNotEqual(self.app.cookies['gimlet'], orig_cookie)
        self.assertNotEqual(self.app.cookies['gimlet'], mangled_cookie)

    def test_mutate(self):
        # First set a key.
        res = self.app.get('/mutate_set')
        self.assertIn('Set-Cookie', res.headers)
        # Check it
        res = self.app.get('/mutate_get')
        self.assertEqual(res.body, 'bar:42')
        # Update the key without saving
        res = self.app.get('/mutate_nosave')
        res.mustcontain('mutate_nosave')
        # Check again, it shouldn't be saved
        res = self.app.get('/mutate_get')
        self.assertEqual(res.body, 'bar:42')
        # Now update the key with saving
        res = self.app.get('/mutate_save')
        res.mustcontain('mutate_save')
        # Check again, it should be saved
        res = self.app.get('/mutate_get')
        self.assertEqual(res.body, 'bar:42,foo:123')
