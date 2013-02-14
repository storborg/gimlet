from datetime import datetime

from .crypto import Crypter
from .serializer import URLSafeCookieSerializer
from .session import Session
from .util import parse_settings


def session_factory_factory(secret,
                            backend=None,
                            clientside=None,
                            cookie_name='gimlet',
                            encryption_key=None,
                            fake_https=False,
                            permanent=False,
                            secure=False):
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

    return type('SessionFactory', (Session,), {

        'backend': backend,

        'channel_names': {
            'insecure': cookie_name,
            'secure_perm': cookie_name + '-sp',
            'secure_nonperm': cookie_name + '-sn'
        },

        'channel_opts': {
            'insecure': {'expires': future},
            'secure_perm': {'secure': (not fake_https), 'expires': future},
            'secure_nonperm': {'secure': (not fake_https)},
        },

        'cookie_name': cookie_name,

        'defaults': {
            'secure': secure,
            'permanent': permanent,
            'clientside': clientside,
        },

        'serializer': URLSafeCookieSerializer(secret, backend, crypter),
    })


def session_factory_from_settings(settings, prefix='gimlet.'):
    """Configure a :class:`.session.Session` from ``settings``.

    See :func:`.util.parse_settings` for more info on how the
    ``settings`` is parsed.

    """
    options = parse_settings(settings, prefix)
    return session_factory_factory(**options)
