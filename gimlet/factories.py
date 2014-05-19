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
                            enable_http=True,
                            enable_https=True,
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

    configuration = {

        'backend': backend,

        'channel_names': {
        },

        'channel_opts': {
        },

        'cookie_name': cookie_name,

        'defaults': {
            'secure': secure,
            'permanent': permanent,
            'clientside': clientside,
        },

        'serializer': URLSafeCookieSerializer(secret, backend, crypter),
    }

    assert enable_http or enable_https, "at least one scheme must be enabled"

    if enable_http:
        configuration['channel_names']['insecure'] = cookie_name
        configuration['channel_opts']['insecure'] = {'expires': future}

    if enable_https:
        configuration['channel_names']['secure_perm'] = cookie_name + '-sp'
        configuration['channel_names']['secure_nonperm'] = cookie_name + '-sn'
        configuration['channel_opts']['secure_perm'] = \
            {'secure': (not fake_https), 'expires': future}
        configuration['channel_opts']['secure_nonperm'] = \
            {'secure': (not fake_https)}

    return type('SessionFactory', (Session,), configuration)


def session_factory_from_settings(settings, prefix='gimlet.'):
    """Configure a :class:`.session.Session` from ``settings``.

    See :func:`.util.parse_settings` for more info on how the
    ``settings`` is parsed.

    """
    options = parse_settings(settings, prefix)
    return session_factory_factory(**options)
