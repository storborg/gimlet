from datetime import datetime, timedelta
from unittest import TestCase

from webob import Request, Response
from webob.exc import HTTPNotFound
from webtest import TestApp

from gimlet.middleware import SessionMiddleware


class SampleApp(object):

    """A WSGI app that manipulates the session.

    It provides actions which mimic the dict-like interface of
    :class:`gimlet.session.Session`.

    Hitting the URL ``/set/foo/bar`` will set 'foo' => 'bar' in the session
    and return 'ok'.

    Hitting the URL ``/get/foo`` will then return 'bar'.

    Getting a key which has not been set will return a 404.

    """

    def __call__(self, environ, start_response):
        req = Request(environ)
        path_info_parts = req.path_info.strip('/').split('/')
        action_name = path_info_parts[0]

        req.matchdict = {'action': action_name}
        try:
            req.matchdict['key'] = path_info_parts[1]
            req.matchdict['value'] = path_info_parts[2]
        except IndexError:
            pass

        # Options passed to ``Session.get()``, et al
        req.options = {k: bool(int(v)) for k, v in req.params.items()}

        action = getattr(self, action_name)
        sess = req.environ['gimlet.session']

        resp = action(req, sess)
        if isinstance(resp, basestring):
            resp = Response(resp)
        resp.content_type = 'text/plain'
        return resp(environ, start_response)

    def set(self, req, sess):
        sess.set(req.matchdict['key'], req.matchdict['value'], **req.options)
        return 'ok'

    def get(self, req, sess):
        key = req.matchdict['key']
        if req.options:
            val = sess.get(key, **req.options)
        else:
            try:
                val = sess[key]
            except KeyError:
                return HTTPNotFound('key %s not found' % key)
        return str(val)

    def has(self, req, sess):
        return str(req.matchdict['key'] in sess).lower()

    def append(self, req, sess):
        key = req.matchdict['key']
        sess.setdefault(key, [])
        sess[key].append(req.matchdict['value'])
        sess.save()
        return 'ok'

    def flatten(self, req, sess):
        return ':'.join(sess[req.matchdict['key']])

    def is_secure(self, req, sess):
        return str(sess.is_secure(req.matchdict['key']))

    def is_permanent(self, req, sess):
        return str(sess.is_permanent(req.matchdict['key']))

    def delete(self, req, sess):
        key = req.matchdict['key']
        try:
            del sess[key]
        except KeyError:
            return HTTPNotFound('key %s not found' % key)
        return 'ok'

    def id(self, req, sess):
        return str(sess.id)

    def time(self, req, sess):
        return str(sess.created_time)

    def timestamp(self, req, sess):
        return str(sess.created_timestamp)

    def len(self, req, sess):
        return str(len(sess))

    def iter(self, req, sess):
        return '\n'.join(iter(sess))

    def repr(self, req, sess):
        return repr(sess)


inner_app = SampleApp()


class TestActions(TestCase):

    def setUp(self):
        self.backend = {}
        wrapped_app = SessionMiddleware(
            inner_app, 's3krit', backend=self.backend)
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

        resp = self.app.get('https://localhost/get/tree?secure=1&permanent=0')
        self.assertEqual(resp.body, 'None')

        resp = self.app.get('https://localhost/get/tree?secure=1&permanent=1')
        resp.mustcontain('beard')

        channel_keys = set()
        for channel in self.backend.values():
            self.assertEqual(len(channel.keys()), 1)
            channel_keys.add(channel.keys()[0])

        self.assertEqual(set(channel_keys), set(['uruk', 'tree']))

        resp = self.app.get('https://localhost/get/uruk?secure=0')
        self.assertEqual(resp.body, 'None')

    def test_set_insecure_nonpermanent_fails(self):
        with self.assertRaises(ValueError):
            self.app.get('/set/gimli/bogus-value?secure=0&permanent=0')

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

        self.assertIn('max-age=', cookies['gimlet-sp'])
        self.assertNotIn('max-age', cookies['gimlet-sn'])
        self.assertIn('max-age', cookies['gimlet'])
        self.assertNotIn('expires', cookies['gimlet-sn'])
        self.assertIn('expires', cookies['gimlet'])

        # XXX Assert that ``gimlet`` and ``gimlet-sp`` cookies are effectively
        # permanent.

    def test_set_clientside(self):
        resp = self.app.get('/set/foo/bar?clientside=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/get/foo')
        resp.mustcontain('bar')

    def test_set_clientside_secure(self):
        resp = self.app.get(
            'https://localhost/set/foo/bar?clientside=1&secure=1')
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

        resp = self.app.get('/get/greeting?clientside=1')
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
        self.app.get(
            'https://localhost/set/samwise/gamgee?secure=1&permanent=1')
        self.app.get(
            'https://localhost/set/peregrin/took?secure=1&clientside=1')

        resp = self.app.get('https://localhost/repr')
        resp.mustcontain('frodo')
        resp.mustcontain('meriadoc')
        resp.mustcontain('samwise')
        resp.mustcontain('peregrin')

    def test_mutate(self):
        self.app.get('/append/spider/itsy')
        self.app.get('/append/spider/bitsy')
        resp = self.app.get('/flatten/spider')
        resp.mustcontain('itsy:bitsy')


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
            app.get('/set/quux/bogus-value?clientside=0')

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
