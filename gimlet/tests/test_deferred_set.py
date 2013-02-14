from unittest import TestCase

from webob import Request, Response
from webtest import TestApp

from gimlet.middleware import SessionMiddleware


class DeferredSetApp(object):
    """
    This is a sample app which tries to set a session key AFTER returning the
    WSGI response, by returning a generator, and setting a key when the
    generator is consumed. This should fail with a ValueError.
    """
    def __call__(self, environ, start_response):
        req = Request(environ)
        sess = req.environ['gimlet.session']

        def do_stuff():
            for ii in range(5):
                yield "%d\n" % ii
            sess.set('foo', 'bar', clientside='clientside' in req.params)

        resp = Response()
        resp.app_iter = do_stuff()
        resp.content_type = 'text/plain'
        return resp(environ, start_response)


inner_app = DeferredSetApp()


class TestNoBackend(TestCase):

    def setUp(self):
        self.inner_app = inner_app
        self.backend = {}
        wrapped_app = SessionMiddleware(
            inner_app, 's3krit', backend=self.backend)
        self.app = TestApp(wrapped_app)

    def test_deferred_set_backend(self):
        resp = self.app.get('/')
        resp.mustcontain('4')
        self.assertEqual(self.backend.values(), [{'foo': 'bar'}])

    def test_deferred_set_client(self):
        with self.assertRaises(ValueError):
            self.app.get('/?clientside=1')
