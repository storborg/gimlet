from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
import logging

import abc
import itertools
import os
import time

from binascii import hexlify
from datetime import datetime
from collections import MutableMapping

from itsdangerous import BadSignature

log = logging.getLogger('gimlet')


# Used by :meth:`Session.get` to detect when no options are explicitly
# passed.
DEFAULT = object()


class Session(MutableMapping):

    """Abstract front end for multiple session channels."""

    # Subclasses need to define all of these
    backend = abc.abstractproperty
    channel_names = abc.abstractproperty
    channel_opts = abc.abstractproperty
    cookie_name = abc.abstractproperty
    defaults = abc.abstractproperty
    serializer = abc.abstractproperty

    def __init__(self, request):
        self.request = request
        self.flushed = False

        channels = {}
        for key in self.channel_names:
            channels[key] = self.read_channel(key)
        self.channels = channels

        self.has_backend = all(
            (ch.backend is not None) for ch in channels.values())

    @property
    def default_channel(self):
        return self.channels['perm']

    @property
    def id(self):
        return self.default_channel.id

    @property
    def created_timestamp(self):
        return self.default_channel.created_timestamp

    @property
    def created_time(self):
        return self.default_channel.created_time

    def response_callback(self, request, response):
        self.flushed = True
        for key in self.channels:
            self.write_channel(request, response, key, self.channels[key])

    def __getitem__(self, key):
        """Get value for ``key`` from the first channel it's found in."""
        for channel in self.channels.values():
            try:
                return channel.get(key)
            except KeyError:
                pass
        raise KeyError(key)

    def _check_options(self, permanent, clientside):
        # If no backend is present, don't allow explicitly setting a key as
        # non-clientside.
        if (not self.has_backend) and (clientside is False):
            raise ValueError('setting a non-clientside key with no backend '
                             'present is not supported')

        if permanent is None:
            permanent = self.defaults['permanent']
        if clientside is None:
            clientside = self.defaults['clientside']

        if self.flushed and clientside:
            raise ValueError('clientside keys cannot be set after the WSGI '
                             'response has been returned')

        if permanent:
            channel_key = 'perm'
        else:
            channel_key = 'nonperm'

        return self.channels[channel_key], clientside

    def get(self, key, default=None, permanent=DEFAULT, clientside=DEFAULT):
        """Get value for ``key`` or ``default`` if ``key`` isn't present.

        When no options are passed, this behaves like `[]`--it will return
        the value for ``key`` from the first channel it's found in.

        On the other hand, if *any* option is specified, this will check
        *all* of the options, set defaults for those that aren't passed,
        then try to get the value from a specific channel.

        In either case, if ``key`` isn't present, the ``default`` value is
        returned, just like a normal ``dict.get()``.

        """
        options = permanent, clientside
        if all(opt is DEFAULT for opt in options):
            action = lambda: self[key]
        else:
            options = (opt if opt is not DEFAULT else None for opt in options)
            channel, clientside = self._check_options(*options)
            action = lambda: channel.get(key, clientside=clientside)
        try:
            return action()
        except KeyError:
            return default

    def __setitem__(self, key, val):
        return self.set(key, val)

    def set(self, key, val, permanent=None, clientside=None):
        if key in self:
            del self[key]
        channel, clientside = self._check_options(permanent, clientside)
        channel.set(key, val, clientside=clientside)

        # If the response has already been flushed, we need to explicitly
        # persist this set to the backend.
        if self.flushed:
            channel.backend_write()

    def save(self, permanent=None, clientside=None):
        channel, clientside = self._check_options(permanent, clientside)
        if clientside:
            channel.client_dirty = True
        else:
            channel.backend_dirty = True

    def __delitem__(self, key):
        if key not in self:
            raise KeyError(key)
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
        return key in self.channels.get('perm', {})

    def __repr__(self):
        keys = '\n'.join(["-- %s --\n%r" % (k, v) for k, v in
                          self.channels.items()])
        return "<Session \n%s\n>" % keys

    def make_session_id(self):
        return hexlify(os.urandom(16))

    def read_channel(self, key):
        name = self.channel_names[key]
        if name in self.request.cookies:
            try:
                id, created_timestamp, client_data = \
                    self.serializer.loads(self.request.cookies[name])
            except BadSignature as e:
                log.warn('Request from %s contained bad sig. %s',
                         self.request.remote_addr, e)
                return self.fresh_channel()
            else:
                return SessionChannel(id, created_timestamp, self.backend,
                                      fresh=False, client_data=client_data)
        else:
            return self.fresh_channel()

    def write_channel(self, req, resp, key, channel):
        name = self.channel_names[key]

        # Set a cookie IFF the following conditions:
        # - data has been changed on the client
        # OR
        # - the cookie is fresh
        if channel.client_dirty or channel.fresh:
            resp.set_cookie(name,
                            self.serializer.dumps(channel),
                            httponly=True,
                            secure=req.scheme == 'https',
                            **self.channel_opts[key])

        # Write to the backend IFF the following conditions:
        # - data has been changed on the backend
        if channel.backend_dirty:
            channel.backend_write()

    def fresh_channel(self):
        return SessionChannel(
            self.make_session_id(), int(time.time()), self.backend, fresh=True)

    def invalidate(self):
        self.clear()
        for key in self.channels:
            self.channels[key] = self.fresh_channel()

    # Flash & CSRF methods taken directly from pyramid_beaker.
    # These are part of the Pyramid Session API.

    def flash(self, msg, queue='', allow_duplicate=True):
        storage = self.setdefault('_f_' + queue, [])
        if allow_duplicate or (msg not in storage):
            storage.append(msg)

    def pop_flash(self, queue=''):
        storage = self.pop('_f_' + queue, [])
        return storage

    def peek_flash(self, queue=''):
        storage = self.get('_f_' + queue, [])
        return storage

    def new_csrf_token(self):
        token = hexlify(os.urandom(20))
        self['_csrft_'] = token
        return token

    def get_csrf_token(self):
        token = self.get('_csrft_', None)
        if token is None:
            token = self.new_csrf_token()
        return token


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
