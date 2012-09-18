import os
import time
import itertools
import cPickle as pickle

from struct import Struct
from datetime import datetime
from collections import MutableMapping

from webob import Request
from itsdangerous import Serializer, URLSafeSerializerMixin


class Session(MutableMapping):

    def __init__(self, id, created_timestamp, backend, fresh,
                 client_data=None):
        self.dirty_keys = set()
        self.id = id
        self.created_timestamp = created_timestamp
        self.backend = backend
        self.fresh = fresh

        self.client_data = client_data or {}
        self.client_dirty = False

        self.backend_data = {}
        self.backend_dirty = False
        self.backend_loaded = False

    def backend_read(self):
        if not self.backend_loaded:
            try:
                self.backend_data = self.backend[self.id]
            except KeyError:
                self.backend_data = {}
            self.backend_loaded = True

    def backend_write(self):
        self.backend[self.id] = self.backend_data

    @property
    def created_time(self):
        return datetime.utcfromtimestamp(self.created_timestamp)

    def __iter__(self):
        self.backend_read()
        return itertools.chain(iter(self.client_data), iter(self.backend_data))

    def __len__(self):
        self.backend_read()
        return len(self.backend_data) + len(self.client_data)

    def __getitem__(self, key):
        return self.get(key)

    def get(self, key, clientside=None):
        if (key in self.client_data) or clientside:
            return self.client_data[key]
        else:
            self.backend_read()
            return self.backend_data[key]

    def __setitem__(self, key, value):
        return self.set(key, value)

    def set(self, key, value, clientside=None):
        if clientside:
            self.client_data[key] = value
            self.client_dirty = True
        else:
            self.backend_data[key] = value
            self.backend_dirty = True

    def __delitem__(self, key):
        if key in self.client_data:
            del self.client_data[key]
            self.client_dirty = True
        else:
            self.backend_read()
            del self.backend_data[key]
            self.backend_dirty = True


class CookieSerializer(Serializer):
    packer = Struct('16si')

    def __init__(self, secret, backend):
        Serializer.__init__(self, secret)
        self.backend = backend

    def load_payload(self, payload):
        """
        Convert a cookie into a Session instance.
        """
        raw_id, created_timestamp = \
            self.packer.unpack(payload[:self.packer.size])
        client_data_pkl = payload[self.packer.size:]

        id = raw_id.encode('hex')
        client_data = pickle.loads(client_data_pkl)
        return Session(id, created_timestamp, self.backend,
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
                 cookie_name='gimlet', environ_key='gimlet.session'):
        self.app = app
        self.backend = backend

        self.cookie_name = cookie_name
        self.environ_key = environ_key

        self.serializer = URLSafeCookieSerializer(secret, backend)

    def make_session_id(self):
        return os.urandom(16).encode('hex')

    def new_session(self):
        id = self.make_session_id()
        return Session(id, int(time.time()), self.backend, fresh=True)

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
