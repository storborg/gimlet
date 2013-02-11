import itertools

from datetime import datetime
from collections import MutableMapping


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

    def get(self, key, default=None,
            secure=None, permanent=None, clientside=None):
        channel, clientside = self._check_options(secure, permanent,
                                                  clientside)
        try:
            return channel.get(key, clientside=clientside)
        except KeyError:
            return default

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
