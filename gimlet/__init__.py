import os
import time
import pickle

from collections import MutableMapping

from webob import Request
from itsdangerous import Signer


class Session(MutableMapping):

    def __init__(self, id, backend, client_keys, fresh, client_data=None):
        self.dirty_keys = set()
        self.id = id
        self.backend = backend
        self.client_keys = client_keys
        self.fresh = fresh

        self.data = client_data or {}

        self.client_dirty = False
        self.backend_dirty = False
        self.loaded = False

        # If there are any keys set in client_data that aren't in client_keys,
        # they need to be moved from client to server, so mark both as dirty.
        keys = set(self.data.keys())
        if not keys.issubset(client_keys):
            assert not self.fresh, ("can't create initial session with "
                                    "server-resident keys: %r" % client_data)
            self.client_dirty = self.backend_dirty = True

    def backend_read(self):
        if not self.loaded:
            data = self.backend.get(self.id, {})
            # For each key, we need to check if it's in the set of client keys.
            # If so, both the client and backend sets are dirty, since the key
            # needs to be moved from backend to client.
            for key, val in data.iteritems():
                if key in self.client_keys:
                    self.client_dirty = self.backend_dirty = True
                self.data.setdefault(key, val)
            self.loaded = True

    def backend_write(self):
        self.backend[self.id] = self.backend_data

    @property
    def client_data(self):
        return {k: v for k, v in self.data.iteritems()
                if k in self.client_keys}

    @property
    def backend_data(self):
        return {k: v for k, v in self.data.iteritems()
                if k not in self.client_keys}

    def mark_dirty(self, key):
        if key in self.client_keys:
            self.client_dirty = True
        else:
            self.backend_dirty = True

    def __iter__(self):
        self.backend_read()
        return iter(self.data)

    def __len__(self):
        self.backend_read()
        return len(self.data)

    def __getitem__(self, key):
        if key not in self.data:
            self.backend_read()
        return self.data[key]

    def __setitem__(self, key, value):
        self.mark_dirty(key)
        self.data[key] = value

    def __delitem__(self, key):
        if key not in self.client_keys:
            self.backend_read()
        self.mark_dirty(key)
        del self.data[key]


class SessionMiddleware(object):
    def __init__(self, app, secret, backend,
                 cookie_name='gimlet', environ_key='gimlet.session',
                 secure=True, cookie_expires=True, client_keys=None,
                 created_key=None):
        self.app = app
        self.signer = Signer(secret)
        self.backend = backend

        self.cookie_name = cookie_name
        self.environ_key = environ_key
        self.secure = secure
        self.cookie_expires = cookie_expires

        self.created_key = created_key
        self.client_keys = set(client_keys or [])

    def deserialize(self, raw_cookie):
        # FIXME Use something better than pickle here.
        id, client_data = pickle.loads(raw_cookie)
        return Session(id, self.backend, self.client_keys, fresh=False,
                       client_data=client_data)

    def serialize(self, sess):
        # FIXME Use something better than pickle here.
        return pickle.dumps([sess.id, sess.client_data])

    def make_session_id(self):
        return os.urandom(16).encode('hex')

    def new_session(self):
        id = self.make_session_id()
        return Session(id, self.backend, self.client_keys, fresh=True)

    def __call__(self, environ, start_response):
        req = Request(environ)

        if self.cookie_name in req.cookies:
            raw_cookie = self.signer.unsign(req.cookies[self.cookie_name])
            sess = self.deserialize(raw_cookie)
        else:
            sess = self.new_session()
            if self.created_key:
                sess[self.created_key] = time.time()

        req.environ[self.environ_key] = sess

        resp = req.get_response(self.app)

        # Set a cookie IFF the following conditions:
        # - data has been changed on the client
        # OR
        # - the cookie is fresh AND data has been changed on the backend
        if sess.client_dirty or (sess.fresh and sess.backend_dirty):
            raw_cookie = self.serialize(sess)
            resp.set_cookie(self.cookie_name, self.signer.sign(raw_cookie))

        # Write to the backend IFF the following conditions:
        # - data has been changed on the backend
        if sess.backend_dirty:
            sess.backend_write()

        return resp(environ, start_response)
