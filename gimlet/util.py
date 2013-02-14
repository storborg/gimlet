from importlib import import_module
from inspect import getmembers, isclass

from .backends.base import BaseBackend


def parse_settings(settings, prefix='gimlet.'):
    """Parse settings and return options.

    ``settings`` is a dict that contains options for
    :func:`.factories.session_factory_factory`. Settings that
    don't start with ``prefix`` will be ignored. As a convenience, some
    of the options in ``settings`` may be specified as strings.

    All of the boolean options can be passed as strings, which will be
    parsed by :func:`asbool`.

    If `backend` is a string, it must be the name of a module containing
    a subclass of :class:`.backends.base.BaseBackend`. If the name
    contains one or more dots, it will be considered absolute;
    otherwise, it will be considered relative to :mod:`.backends`.

    """
    options = {}
    bool_options = ('clientside', 'fake_https', 'permanent', 'secure')
    for k, v in settings.items():
        if k.startswith(prefix):
            k = k[len(prefix):]
            if k in bool_options:
                v = asbool(v)
            options[k] = v
    if 'secret' not in options:
        raise ValueError('secret is required')
    if 'backend' in options and options['backend'] is not None:
        backend = options['backend']
        if isinstance(backend, basestring):
            predicate = lambda m: (
                isclass(m) and
                issubclass(m, BaseBackend) and
                (m is not BaseBackend))
            module_name = backend
            if '.' not in module_name:
                module_name = 'gimlet.backends.' + backend
            backend_module = import_module(module_name)
            backend_cls = getmembers(backend_module, predicate)[0][1]
            options['backend'] = backend_cls
        backend = options['backend']
        if not (isclass(backend) and issubclass(backend, BaseBackend)):
            raise ValueError('backend must be a subclass of BaseBackend')
    backend_cls = options.get('backend')
    if backend_cls is not None:
        backend_options = {}
        for k in options.keys():
            if k.startswith('backend.'):
                backend_options[k[8:]] = options.pop(k)
        options['backend'] = options['backend'](**backend_options)
    return options


def asbool(s):
    """Convert value to bool. Copied from pyramid.settings."""
    if s is None:
        return False
    if isinstance(s, bool):
        return s
    s = str(s).strip()
    return s.lower() in ('t', 'true', 'y', 'yes', 'on', '1')
