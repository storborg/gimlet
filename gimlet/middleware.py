import os
import time

from datetime import datetime

from webob import Request

from .crypto import Crypter
from .serializer import URLSafeCookieSerializer
from .session import Session, SessionChannel


class SessionMiddleware(object):
    def __init__(self, app, secret, backend=None, encryption_key=None,
                 cookie_name='gimlet', environ_key='gimlet.session',
                 secure=False, permanent=False, clientside=None,
                 fake_https=False):
        self.app = app
        self.backend = backend

        if backend is None:
            if clientside is False:
                raise ValueError('cannot configure middleware default of '
                                 'clientside=False with no backend present')
            clientside = True
        else:
            clientside = bool(clientside)

        self.cookie_name = cookie_name
        self.environ_key = environ_key

        self.defaults = dict(secure=secure,
                             permanent=permanent,
                             clientside=clientside)

        if encryption_key:
            crypter = Crypter(encryption_key)
        else:
            crypter = None

        self.serializer = URLSafeCookieSerializer(secret, backend, crypter)

        self.channel_names = {
            'insecure': self.cookie_name,
            'secure_perm': self.cookie_name + '-sp',
            'secure_nonperm': self.cookie_name + '-sn'
        }

        future = datetime.fromtimestamp(0x7FFFFFFF)
        self.channel_opts = {
            'insecure': dict(expires=future),
            'secure_perm': dict(secure=(not fake_https), expires=future),
            'secure_nonperm': dict(secure=(not fake_https)),
        }

    def make_session_id(self):
        return os.urandom(16).encode('hex')

    def read_channel(self, req, key):
        name = self.channel_names[key]
        if name in req.cookies:
            id, created_timestamp, client_data = \
                self.serializer.loads(req.cookies[name])
            return SessionChannel(id, created_timestamp, self.backend,
                                  fresh=False, client_data=client_data)
        else:
            id = self.make_session_id()
            return SessionChannel(id, int(time.time()), self.backend,
                                  fresh=True)

    def write_channel(self, resp, key, channel):
        name = self.channel_names[key]

        # Set a cookie IFF the following conditions:
        # - data has been changed on the client
        # OR
        # - the cookie is fresh
        if channel.client_dirty or channel.fresh:
            resp.set_cookie(name, self.serializer.dumps(channel),
                            httponly=True, **self.channel_opts[key])

        # Write to the backend IFF the following conditions:
        # - data has been changed on the backend
        if channel.backend_dirty:
            channel.backend_write()

    def __call__(self, environ, start_response):
        req = Request(environ)

        channels = {}
        for key in self.channel_names:
            if (not self.channel_opts[key].get('secure') or
                    req.scheme == 'https'):
                channels[key] = self.read_channel(req, key)

        sess = req.environ[self.environ_key] = Session(channels, self.defaults)

        resp = req.get_response(self.app)

        sess.flushed = True

        for key in channels:
            self.write_channel(resp, key, channels[key])

        return resp(environ, start_response)
