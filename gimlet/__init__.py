import os
import time
import cPickle as pickle

from struct import Struct
from datetime import datetime
from collections import MutableMapping

from webob import Request
from itsdangerous import Serializer, URLSafeSerializerMixin


class Session(MutableMapping):

    def __init__(self, id, created_timestamp, backend, client_keys, fresh,
                 client_data=None):
        self.dirty_keys = set()
        self.id = id
        self.created_timestamp = created_timestamp
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
            try:
                data = self.backend[self.id]
            except KeyError:
                data = {}
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

    @property
    def created_time(self):
        return datetime.utcfromtimestamp(self.created_timestamp)

    def __iter__(self):
        self.backend_read()
        return iter(self.data)

    def __len__(self):
        self.backend_read()
        return len(self.data)

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key):
        if key not in self.data:
            self.backend_read()
        return self.data[key]

    def __setitem__(self, key, value):
        return self.set(key, value)

    def set(self, key, value):
        self.mark_dirty(key)
        self.data[key] = value

    def __delitem__(self, key):
        if key not in self.client_keys:
            self.backend_read()
        self.mark_dirty(key)
        del self.data[key]


class CookieSerializer(Serializer):
    packer = Struct('16si')

    def __init__(self, secret, backend, client_keys):
        Serializer.__init__(self, secret)
        self.backend = backend
        self.client_keys = client_keys

    def load_payload(self, payload):
        """
        Convert a cookie into a Session instance.
        """
        raw_id, created_timestamp = \
            self.packer.unpack(payload[:self.packer.size])
        client_data_pkl = payload[self.packer.size:]

        id = raw_id.encode('hex')
        client_data = pickle.loads(client_data_pkl)
        return Session(id, created_timestamp, self.backend, self.client_keys,
                       fresh=False, client_data=client_data)

    def dump_payload(self, sess):
        """
        Convert a Session instance into a cookie by packing it precisely into a
        string.
        """
        client_data_pkl = pickle.dumps(sess.client_data)
        raw_id = sess.id.decode('hex')
        return (self.packer.pack(raw_id, sess.created_timestamp) +
                client_data_pkl)


class URLSafeCookieSerializer(URLSafeSerializerMixin, CookieSerializer):
    pass


class SessionMiddleware(object):
    def __init__(self, app, secret, backend,
                 cookie_name='gimlet', environ_key='gimlet.session',
                 secure=True, client_keys=None):
        self.app = app
        self.backend = backend

        self.cookie_name = cookie_name
        self.environ_key = environ_key
        self.secure = secure

        self.client_keys = set(client_keys or [])
        self.serializer = URLSafeCookieSerializer(secret, backend,
                                                  self.client_keys)

    def make_session_id(self):
        return os.urandom(16).encode('hex')

    def new_session(self):
        id = self.make_session_id()
        return Session(id, int(time.time()), self.backend, self.client_keys,
                       fresh=True)

    def __call__(self, environ, start_response):
        req = Request(environ)

        if self.cookie_name in req.cookies:
            sess = self.serializer.loads(req.cookies[self.cookie_name])
        else:
            sess = self.new_session()

        req.environ[self.environ_key] = sess

        resp = req.get_response(self.app)

        # Set a cookie IFF the following conditions:
        # - data has been changed on the client
        # OR
        # - the cookie is fresh AND data has been changed on the backend
        if sess.client_dirty or (sess.fresh and sess.backend_dirty):
            resp.set_cookie(self.cookie_name, self.serializer.dumps(sess))

        # Write to the backend IFF the following conditions:
        # - data has been changed on the backend
        if sess.backend_dirty:
            sess.backend_write()

        return resp(environ, start_response)
