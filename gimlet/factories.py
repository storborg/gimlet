from __future__ import (absolute_import, division, print_function,
                        unicode_literals)
from datetime import datetime

from .crypto import Crypter
from .serializer import URLSafeCookieSerializer
from .session import Session
from .util import parse_settings


def session_factory_factory(secret,
                            backend=None,
                            clientside=None,
                            cookie_name_temporary='gimlet-n',
                            cookie_name_permanent='gimlet-p',
                            encryption_key=None,
                            permanent=False):
    """Configure a :class:`.session.Session` subclass."""
    if backend is None:
        if clientside is False:
            raise ValueError('cannot configure default of clientside=False '
                             'with no backend present')
        clientside = True
    else:
        clientside = bool(clientside)

    if encryption_key:
        crypter = Crypter(encryption_key)
    else:
        crypter = None

    future = datetime.fromtimestamp(0x7FFFFFFF)

    configuration = {

        'backend': backend,

        'channel_names': {
        },

        'channel_opts': {
        },

        'defaults': {
            'permanent': permanent,
            'clientside': clientside,
        },

        'serializer': URLSafeCookieSerializer(secret, backend, crypter),
    }

    configuration['channel_names']['perm'] = cookie_name_permanent
    configuration['channel_names']['nonperm'] = cookie_name_temporary
    configuration['channel_opts']['perm'] = {'expires': future}
    configuration['channel_opts']['nonperm'] = {}

    return type(str('SessionFactory'), (Session,), configuration)


def session_factory_from_settings(settings, prefix='gimlet.'):
    """Configure a :class:`.session.Session` from ``settings``.

    See :func:`.util.parse_settings` for more info on how the
    ``settings`` is parsed.

    """
    options = parse_settings(settings, prefix)
    return session_factory_factory(**options)
