import os
import time
import itertools
import cPickle as pickle

from struct import Struct
from datetime import datetime
from collections import MutableMapping

from webob import Request
from itsdangerous import Serializer, URLSafeSerializerMixin

from .crypto import Crypter


class Session(MutableMapping):

    def __init__(self, channels, defaults):
        self.flushed = False
        self.channels = channels
        self.defaults = defaults
        self.has_backend = all((ch.backend is not None) for ch in
                               self.channels.values())

    @property
    def id(self):
        return self.channels['insecure'].id

    @property
    def created_timestamp(self):
        return self.channels['insecure'].created_timestamp

    @property
    def created_time(self):
        return self.channels['insecure'].created_time

    def __getitem__(self, key):
        for channel in self.channels.values():
            try:
                return channel.get(key)
            except KeyError:
                pass
        raise KeyError

    def _check_options(self, secure, permanent, clientside):
        # If permanent is explicitly specified as False, ensure that secure is
        # not explicitly set to False.
        if (secure is False) and (permanent is False):
            raise ValueError('setting non-secure non-permanent keys is not '
                             'supported')

        # If no backend is present, don't allow explicitly setting a key as
        # non-clientside.
        if (not self.has_backend) and (clientside is False):
            raise ValueError('setting a non-clientside key with no backend '
                             'present is not supported')

        if secure is None:
            secure = self.defaults['secure']
        if permanent is None:
            permanent = self.defaults['permanent']
        if clientside is None:
            clientside = self.defaults['clientside']

        if self.flushed and clientside:
            raise ValueError('clientside keys cannot be set after the WSGI '
                             'response has been returned')

        channel_key = 'insecure'
        if secure:
            if 'secure_perm' not in self.channels:
                raise ValueError('cannot set a secure key outside of https '
                                 'context, unless fake_https is used.')
            if permanent:
                channel_key = 'secure_perm'
            else:
                channel_key = 'secure_nonperm'

        return self.channels[channel_key], clientside

    def get(self, key, secure=None, permanent=None, clientside=None):
        channel, clientside = self._check_options(secure, permanent,
                                                  clientside)
        return channel.get(key, clientside=clientside)

    def __setitem__(self, key, val):
        return self.set(key, val)

    def set(self, key, val, secure=None, permanent=None, clientside=None):
        if key in self:
            del self[key]
        channel, clientside = self._check_options(secure, permanent,
                                                  clientside)
        channel.set(key, val, clientside=clientside)

        # If the response has already been flushed, we need to explicitly
        # persist this set to the backend.
        if self.flushed:
            channel.backend_write()

    def __delitem__(self, key):
        if key not in self:
            raise KeyError
        for channel in self.channels.values():
            if key in channel:
                channel.delete(key)

    def __contains__(self, key):
        return any((key in channel) for channel in self.channels.values())

    def __iter__(self):
        return itertools.chain(*[iter(ch) for ch in self.channels.values()])

    def __len__(self):
        return sum([len(ch) for ch in self.channels.values()])

    def is_permanent(self, key):
        return ((key in self.channels.get('secure_perm', {})) or
                (key in self.channels['insecure']))

    def is_secure(self, key):
        return ((key in self.channels.get('secure_nonperm', {})) or
                (key in self.channels.get('secure_perm', {})))

    def __repr__(self):
        keys = '\n'.join(["-- %s --\n%r" % (k, v) for k, v in
                          self.channels.iteritems()])
        return "<Session \n%s\n>" % keys


class SessionChannel(object):

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
        if (not self.backend_loaded) and (self.backend is not None):
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

    def get(self, key, clientside=None):
        if ((clientside is None) and (key in self.client_data)) or clientside:
            return self.client_data[key]
        else:
            self.backend_read()
            return self.backend_data[key]

    def set(self, key, value, clientside=None):
        if clientside:
            self.client_data[key] = value
            self.client_dirty = True
        else:
            self.backend_data[key] = value
            self.backend_dirty = True

    def delete(self, key):
        if key in self.client_data:
            del self.client_data[key]
            self.client_dirty = True
        else:
            self.backend_read()
            del self.backend_data[key]
            self.backend_dirty = True

    def __repr__(self):
        self.backend_read()
        return ("id %s\ncreated %s\nbackend %r\nclient %r" %
                (self.id, self.created_time, self.backend_data,
                 self.client_data))


class CookieSerializer(Serializer):
    packer = Struct('16si')

    def __init__(self, secret, backend, crypter):
        Serializer.__init__(self, secret)
        self.backend = backend
        self.crypter = crypter

    def load_payload(self, payload):
        """
        Convert a cookie into a SessionChannel instance.
        """
        if self.crypter:
            payload = self.crypter.decrypt(payload)

        raw_id, created_timestamp = \
            self.packer.unpack(payload[:self.packer.size])
        client_data_pkl = payload[self.packer.size:]

        id = raw_id.encode('hex')
        client_data = pickle.loads(client_data_pkl)
        return SessionChannel(id, created_timestamp, self.backend,
                              fresh=False, client_data=client_data)

    def dump_payload(self, channel):
        """
        Convert a Session instance into a cookie by packing it precisely into a
        string.
        """
        client_data_pkl = pickle.dumps(channel.client_data)
        raw_id = channel.id.decode('hex')
        payload = (self.packer.pack(raw_id, channel.created_timestamp) +
                   client_data_pkl)

        if self.crypter:
            payload = self.crypter.encrypt(payload)

        return payload


class URLSafeCookieSerializer(URLSafeSerializerMixin, CookieSerializer):
    pass


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

        self.channel_opts = {
            'insecure': {},
            'secure_perm': dict(secure=(not fake_https)),
            'secure_nonperm': dict(secure=(not fake_https), max_age=0)
        }

    def make_session_id(self):
        return os.urandom(16).encode('hex')

    def new_session_channel(self):
        id = self.make_session_id()
        return SessionChannel(id, int(time.time()), self.backend, fresh=True)

    def read_channel(self, req, key):
        name = self.channel_names[key]
        if name in req.cookies:
            sc = self.serializer.loads(req.cookies[name])
        else:
            sc = self.new_session_channel()
        return sc

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
