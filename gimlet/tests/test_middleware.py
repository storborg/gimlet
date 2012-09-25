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

    def repr(self, req, sess):
        return Response(repr(sess))


inner_app = SampleApp()


class TestActions(TestCase):

    def setUp(self):
        self.backend = {}
        wrapped_app = SessionMiddleware(inner_app, 's3krit', self.backend)
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

    def test_delete_basic(self):
        resp = self.app.get('/set/foo/blah')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{'foo': 'blah'}])

        resp = self.app.get('/get/foo')
        resp.mustcontain('blah')

        resp = self.app.get('/delete/foo')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{}])

    def test_set_permanent(self):
        resp = self.app.get('/set/boromir/111?permanent=1')
        resp.mustcontain('ok')
        # Ensure that we only have one session, it will correspond to the
        # permanent non-secure cookie.
        self.assertEqual(len(self.app.cookies), 1)
        self.assertEqual(self.backend.values(), [{'boromir': '111'}])

        resp = self.app.get('/get/boromir')
        resp.mustcontain('111')

        resp = self.app.get('https://localhost/is_secure/boromir')
        resp.mustcontain('False')

        resp = self.app.get('/is_permanent/boromir')
        resp.mustcontain('True')

    def test_set_secure_on_http(self):
        with self.assertRaises(ValueError):
            self.app.get('/set/foo/bar?secure=1')

    def test_set_secure_on_https(self):
        resp = self.app.get('https://localhost/set/uruk/hai?secure=1')
        resp.mustcontain('ok')

        self.app.get('/get/uruk', status=404)

        resp = self.app.get('https://localhost/get/uruk')
        resp.mustcontain('hai')

        resp = self.app.get('https://localhost/is_secure/uruk')
        resp.mustcontain('True')

        resp = self.app.get('https://localhost/is_permanent/uruk')
        resp.mustcontain('False')

        self.assertEqual(self.backend.values(), [{'uruk': 'hai'}])

        resp = self.app.get(
            'https://localhost/set/tree/beard?secure=1&permanent=1')
        resp.mustcontain('ok')

        resp = self.app.get('https://localhost/is_secure/tree')
        resp.mustcontain('True')

        resp = self.app.get('https://localhost/is_permanent/tree')
        resp.mustcontain('True')

        self.app.get('https://localhost/get/tree?secure=1&permanent=0',
                     status=404)
        resp = self.app.get('https://localhost/get/tree?secure=1&permanent=1')
        resp.mustcontain('beard')

        channel_keys = set()
        for channel in self.backend.values():
            self.assertEqual(len(channel.keys()), 1)
            channel_keys.add(channel.keys()[0])

        self.assertEqual(set(channel_keys), set(['uruk', 'tree']))

        self.app.get('https://localhost/get/uruk?secure=0', status=404)

    def test_set_insecure_nonpermanent_fails(self):
        with self.assertRaises(ValueError):
            self.app.get('/set/gimli?secure=0&permanent=0')

    def test_cookie_metadata(self):
        resp = self.app.get('https://localhost/set/frodo/ring')
        cookies = {}
        for hdr in resp.headers.getall('Set-Cookie'):
            key, val = hdr.split('=', 1)
            cookies[key] = val.lower()

        self.assertIn('secure', cookies['gimlet-sn'])
        self.assertIn('secure', cookies['gimlet-sp'])
        self.assertNotIn('secure', cookies['gimlet'])

        for cookie in cookies.values():
            self.assertIn('httponly', cookie)

        self.assertIn('max-age=0', cookies['gimlet-sn'])
        self.assertNotIn('max-age', cookies['gimlet-sp'])
        self.assertNotIn('max-age', cookies['gimlet'])
        self.assertNotIn('expires', cookies['gimlet-sp'])
        self.assertNotIn('expires', cookies['gimlet'])

    def test_set_clientside(self):
        resp = self.app.get('/set/foo/bar?clientside=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/get/foo')
        resp.mustcontain('bar')

    def test_set_clientside_secure(self):
        resp = self.app.get('https://localhost/set/foo/bar?clientside=1&secure=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        self.app.get('/get/foo', status=404)

        resp = self.app.get('https://localhost/get/foo')
        resp.mustcontain('bar')

    def test_move_key_from_insecure_to_secure(self):
        resp = self.app.get('/set/greeting/hello')
        resp.mustcontain('ok')

        resp = self.app.get('/get/greeting')
        resp.mustcontain('hello')

        resp = self.app.get('https://localhost/set/greeting/bonjour?secure=1')
        resp.mustcontain('ok')

        resp = self.app.get('https://localhost/get/greeting')
        resp.mustcontain('bonjour')

        self.app.get('/get/greeting', status=404)

    def test_delete_nonexistent(self):
        self.app.get('/delete/foo', status=404)

    def test_move_key_from_clientside_to_serverside(self):
        resp = self.app.get('/set/greeting/aloha?clientside=1')
        resp.mustcontain('ok')

        resp = self.app.get('/get/greeting')
        resp.mustcontain('aloha')

        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/set/greeting/jambo')
        resp.mustcontain('ok')

        resp = self.app.get('/get/greeting')
        resp.mustcontain('jambo')

        self.assertEqual(self.backend.values(), [{'greeting': 'jambo'}])
        self.backend.clear()

        self.app.get('/get/greeting', status=404)

    def test_iter_len(self):
        resp = self.app.get('/set/frodo/baggins?clientside=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/set/gandalf/grey')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [{'gandalf': 'grey'}])

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

    def test_repr(self):
        self.app.get('/set/frodo/baggins')
        self.app.get('https://localhost/set/meriadoc/brandybuck?secure=1')
        self.app.get('https://localhost/set/samwise/gamgee?secure=1&permanent=1')
        self.app.get('https://localhost/set/peregrin/took?secure=1&clientside=1')

        resp = self.app.get('https://localhost/repr')
        resp.mustcontain('frodo')
        resp.mustcontain('meriadoc')
        resp.mustcontain('samwise')
        resp.mustcontain('peregrin')


class TestNoBackend(TestCase):

    def test_getset_basic(self):
        wrapped_app = SessionMiddleware(inner_app, 's3krit')
        app = TestApp(wrapped_app)

        app.get('/get/foo', status=404)

        resp = app.get('/set/foo/bar')
        resp.mustcontain('ok')

        resp = app.get('/get/foo')
        resp.mustcontain('bar')

        with self.assertRaises(ValueError):
            app.get('/set/quux?clientside=0')

    def test_bad_middleware_config(self):
        with self.assertRaises(ValueError):
            SessionMiddleware(inner_app, 's3krit', clientside=False)


class TestFakeHTTPS(TestCase):

    def setUp(self):
        wrapped_app = SessionMiddleware(inner_app, 's3krit', fake_https=True)
        self.app = TestApp(wrapped_app)

    def test_getset_basic(self):
        self.app.get('/get/foo', status=404)

        resp = self.app.get('/set/foo/bar?secure=1')
        resp.mustcontain('ok')

        resp = self.app.get('/get/foo')
        resp.mustcontain('bar')

    def test_cookie_metadata(self):
        resp = self.app.get('https://localhost/set/frodo/ring')
        cookies = {}
        for hdr in resp.headers.getall('Set-Cookie'):
            key, val = hdr.split('=', 1)
            cookies[key] = val.lower()

        self.assertNotIn('secure', cookies['gimlet-sn'])
        self.assertNotIn('secure', cookies['gimlet-sp'])
        self.assertNotIn('secure', cookies['gimlet'])
