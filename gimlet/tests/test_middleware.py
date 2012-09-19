from datetime import datetime, timedelta
from unittest import TestCase

from webob import Request, Response
from webob.exc import HTTPNotFound
from webtest import TestApp

from gimlet import SessionMiddleware


class SampleApp(object):
    """
    This is a sample app which manipulates the session. It provides URL actions
    which mimic the dict-like interface of the session and allow actions
    against keys.

    Hitting the URL /set/foo/bar will set foo=bar in the session and return
    'ok'.

    Hitting the URL /get/foo will then return 'bar'.

    Getting a key which has not been set will return a 404.
    """
    def __call__(self, environ, start_response):
        req = Request(environ)
        sess = req.environ['gimlet.session']
        action = req.path_info_pop()
        req.settings = {k: bool(int(v)) for k, v in req.params.items()}
        resp = getattr(self, action)(req, sess)
        resp.content_type = 'text/plain'
        return resp(environ, start_response)

    def set(self, req, sess):
        key = req.path_info_pop()
        val = req.path_info_pop()
        if req.params:
            sess.set(key, val,
                     clientside=req.settings.get('clientside'),
                     secure=req.settings.get('secure'),
                     permanent=req.settings.get('permanent'))
        else:
            sess[key] = val
        return Response('ok')

    def get(self, req, sess):
        key = req.path_info_pop()
        try:
            if req.params:
                val = sess.get(key,
                               clientside=req.settings.get('clientside'),
                               secure=req.settings.get('secure'),
                               permanent=req.settings.get('permanent'))
            else:
                val = sess[key]
        except KeyError:
            return HTTPNotFound('key %s not found' % key)
        else:
            return Response(str(val))

    def has(self, req, sess):
        key = req.path_info_pop()
        if key in sess:
            return Response('true')
        else:
            return Response('false')

    def is_secure(self, req, sess):
        key = req.path_info_pop()
        return Response(str(sess.is_secure(key)))

    def is_permanent(self, req, sess):
        key = req.path_info_pop()
        return Response(str(sess.is_permanent(key)))

    def delete(self, req, sess):
        key = req.path_info_pop()
        try:
            del sess[key]
        except KeyError:
            return HTTPNotFound('key %s not found' % key)
        else:
            return Response('ok')

    def id(self, req, sess):
        return Response(str(sess.id))

    def time(self, req, sess):
        return Response(str(sess.created_time))

    def timestamp(self, req, sess):
        return Response(str(sess.created_timestamp))

    def len(self, req, sess):
        return Response(str(len(sess)))

    def iter(self, req, sess):
        return Response('\n'.join(iter(sess)))

    def getmany(self, req, sess):
        keys = req.path_info_pop().split('+')
        vals = []
        for key in keys:
            try:
                vals.append(str(sess[key]))
            except KeyError:
                vals.append('?')
        return Response('\n'.join(vals))

    def repr(self, req, sess):
        return Response(repr(sess))


inner_app = SampleApp()


class TestActions(TestCase):

    def setUp(self):
        self.backend = {}
        wrapped_app = SessionMiddleware(inner_app, 's3krit', self.backend,
                                        fake_https=True)
        self.app = TestApp(wrapped_app)

    def test_getset_basic(self):
        self.app.get('/get/foo', status=404)
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/set/foo/bar')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{'foo': 'bar'}])

        resp = self.app.get('/get/foo')
        resp.mustcontain('bar')
        self.assertEqual(self.backend.values(), [{'foo': 'bar'}])

        resp = self.app.get('/delete/foo')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{}])

        self.app.get('/get/foo', status=404)
        self.assertEqual(self.backend.values(), [{}])

    def test_has_basic(self):
        resp = self.app.get('/has/foo')
        resp.mustcontain('false')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/set/foo/blah')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{'foo': 'blah'}])

        resp = self.app.get('/has/foo')
        resp.mustcontain('true')
        self.assertEqual(self.backend.values(), [{'foo': 'blah'}])

    def test_insecure_nonpermanent_fails(self):
        with self.assertRaises(ValueError):
            self.app.get('/set/gimli?secure=0&permanent=0')

    def test_actions_client(self):
        self.app.get('/get/frodo', status=404)
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/has/frodo')
        resp.mustcontain('false')

        resp = self.app.get('/set/frodo/ring?clientside=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        self.app.get('/delete/boromir', status=404)

        resp = self.app.get('/set/boromir/111?clientside=1&secure=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/get/boromir')
        resp.mustcontain('111')

        self.app.get('/get/boromir?secure=0', status=404)
        self.app.get('/get/boromir?secure=1&permanent=1', status=404)
        self.app.get('/get/boromir?secure=1&clientside=0', status=404)

        resp = self.app.get('/is_secure/boromir')
        resp.mustcontain('True')

        resp = self.app.get('/is_permanent/boromir')
        resp.mustcontain('False')

        resp = self.app.get('/set/boromir/333?clientside=1&secure=0')
        resp.mustcontain('ok')

        resp = self.app.get(
            '/set/faramir/222?clientside=1&secure=1&permanent=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/is_permanent/faramir')
        resp.mustcontain('True')

        resp = self.app.get('/get/boromir')
        resp.mustcontain('333')

        resp = self.app.get('/get/faramir')
        resp.mustcontain('222')

        resp = self.app.get('/get/frodo')
        resp.mustcontain('ring')

        resp = self.app.get('/has/frodo')
        resp.mustcontain('true')

        resp = self.app.get('/delete/frodo')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        self.app.get('/get/frodo', status=404)
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/repr')
        resp.mustcontain("u'boromir': u'333'")
        resp.mustcontain("u'faramir': u'222'")

    def test_many(self):
        resp = self.app.get('/set/frodo/baggins?clientside=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/set/gandalf/grey')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{'gandalf': 'grey'}])

        resp = self.app.get('/getmany/frodo+gandalf+legolas')
        resp.mustcontain('baggins')
        resp.mustcontain('grey')
        resp.mustcontain('?')

        resp = self.app.get('/len')
        resp.mustcontain('2')

        resp = self.app.get('/iter')
        resp.mustcontain('frodo')
        resp.mustcontain('gandalf')

    def test_id(self):
        resp = self.app.get('/id')
        self.assertEqual(len(resp.body), 32)

    def test_created_timestamp(self):
        resp = self.app.get('/timestamp')
        timestamp = int(resp.body)

        resp = self.app.get('/time')
        tstring = resp.body

        dt = datetime.utcfromtimestamp(timestamp)

        self.assertEqual(str(dt), tstring)

        utcnow = datetime.utcnow()
        self.assertLess(dt, utcnow)
        self.assertLess(utcnow - dt, timedelta(seconds=3))


class TestNoBackend(TestCase):

    def setUp(self):
        self.inner_app = inner_app
        wrapped_app = SessionMiddleware(inner_app, 's3krit')
        self.app = TestApp(wrapped_app)

    def test_getset_basic(self):
        self.app.get('/get/foo', status=404)

        resp = self.app.get('/set/foo/bar')
        resp.mustcontain('ok')

        resp = self.app.get('/get/foo')
        resp.mustcontain('bar')

        with self.assertRaises(ValueError):
            self.app.get('/set/quux?clientside=0')

    def test_bad_middleware_config(self):
        with self.assertRaises(ValueError):
            SessionMiddleware(self.inner_app, 's3krit', clientside=False)


class TestSecureSet(TestCase):

    def setUp(self):
        wrapped_app = SessionMiddleware(inner_app, 's3krit')
        self.app = TestApp(wrapped_app)

    def test_secure_set_on_http(self):
        with self.assertRaises(ValueError):
            self.app.get('/set/foo/bar?secure=1')

    def test_secure_set_on_https(self):
        resp = self.app.get('https://localhost/set/uruk/hai?secure=1')
        resp.mustcontain('ok')

        self.app.get('/get/uruk', status=404)

        resp = self.app.get('https://localhost/get/uruk')
        resp.mustcontain('hai')
