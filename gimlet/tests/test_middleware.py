from datetime import datetime, timedelta
from unittest import TestCase

from webob import Request, Response
from webob.exc import HTTPNotFound
from webtest import TestApp

from gimlet import SessionMiddleware


class SampleApp(object):
    """
    This is a sample app which manipulates the session. It provides set, get,
    has, and del methods which mimic the dict-like interface of the session and
    allow actions against keys.

    Hitting the URL /set/foo/bar will set foo=bar in the session and return
    'ok'.

    Hitting the URL /get/foo will then return 'bar'.

    Getting a key which has not been set will return a 404.
    """

    def __call__(self, environ, start_response):
        req = Request(environ)
        sess = req.environ['gimlet.session']

        action = req.path_info_pop()

        if action == '':
            resp = Response('hello')
        elif action == 'set':
            key = req.path_info_pop()
            val = req.path_info_pop()
            if req.params.get('clientside'):
                sess.set(key, val, clientside=True)
            else:
                sess[key] = val
            resp = Response('ok')
        elif action == 'get':
            key = req.path_info_pop()
            try:
                val = sess[key]
            except KeyError:
                resp = HTTPNotFound('key %s not found' % key)
            else:
                resp = Response(str(val))
        elif action == 'has':
            key = req.path_info_pop()
            if key in sess:
                resp = Response('true')
            else:
                resp = Response('false')
        elif action == 'del':
            key = req.path_info_pop()
            try:
                del sess[key]
            except KeyError:
                resp = HTTPNotFound('key %s not found' % key)
            else:
                resp = Response('ok')
        elif action == 'id':
            resp = Response(str(sess.id))
        elif action == 'time':
            resp = Response(str(sess.created_time))
        elif action == 'timestamp':
            resp = Response(str(sess.created_timestamp))
        elif action == 'len':
            resp = Response(str(len(sess)))
        elif action == 'iter':
            resp = Response('\n'.join(iter(sess)))
        elif action == 'getmany':
            keys = req.path_info_pop().split('+')
            vals = []
            for key in keys:
                try:
                    vals.append(str(sess[key]))
                except KeyError:
                    vals.append('?')
            resp = Response('\n'.join(vals))

        resp.content_type = 'text/plain'
        return resp(environ, start_response)


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

        resp = self.app.get('/del/foo')
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

    def test_actions_client(self):
        self.app.get('/get/frodo', status=404)
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/has/frodo')
        resp.mustcontain('false')

        resp = self.app.get('/set/frodo/ring?clientside=1')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        resp = self.app.get('/get/frodo')
        resp.mustcontain('ring')

        resp = self.app.get('/has/frodo')
        resp.mustcontain('true')

        resp = self.app.get('/del/frodo')
        resp.mustcontain('ok')
        self.assertEqual(self.backend.values(), [])

        self.app.get('/get/frodo', status=404)
        self.assertEqual(self.backend.values(), [])

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
