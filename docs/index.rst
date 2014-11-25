Gimlet - Better WSGI Sessions
=============================

.. module:: gimlet

Gimlet is a Python infrastructure block to provide versatile key-value
'session' storage for WSGI applications. The design philosophy is 'as fast as
possible with slow components', which is to say, I/O load will be minimized,
but it will work with fairly simple and mature storage backends. It provides:

* Easy setup and configuration
* Key-value dict-like session access
* Multiple backend options, including redis and SQL
* Efficient - absolute minimal I/O load
* Optional client-side storage for a whitelist of keys

It is also:

* 2 oz gin
* 1/2 oz lime juice
* 1/4 oz simple syrup
* lime garnish

Get the `code at GitHub <http://github.com/cartlogic/gimlet>`_.


Quick Start
-----------

Gimlet provides a WSGI Middleware which populates a Session object in the
WSGI environ. The most simple setup looks like::

    from gimlet.middleware import SessionMiddleware
    from gimlet.backends.pyredis import RedisBackend

    backend = RedisBackend()

    app = SuperAwesomeApp()
    app = SessionMiddleware(app, 's3krit', backend)

Inside your app code, you can access the session like::

    session = environ['gimlet.session']
    session['user'] = 'Frodo'

The session data will automatically be persisted at the end of the request.

A unique identifier for the session (also visible to the client) is available
as ``session.id``.


Key Options
-----------

Typical web applications tend to have a concentration of session access on a
relatively small set of keys, with small values. For example, a common session
variable may be a key referencing the logged-in user's account. Gimlet provides
fuctionality to store these commonly-accessed small keys on the clientside, in
the session cookie. This substantially reduces the I/O load of the application
as awhole, without limiting the session flexibility (particularly important for
adapting legacy apps).

To specify that a key should be stored on the client, pass the
``clientside=True`` argument::

    session.set('cart_id', 12345, clientside=True)

.. warning::

    Keys that are stored on the client side are not encrypted by default, so it
    will be possible for eavesdroppers or end users to view their contents.
    They are signed, however, so they cannot be modified without detection. To
    enable encryption of cookies, supply a random 64-char hex string as the
    ``encryption_key`` argument to ``SessionMiddleware``.

Keys can also be set as permanent or not. For example::

    session.set('account_id', 777, permanent=False)

Or, combined::

    session.set('cart_id', 12345, clientside=True, permanent=True)


Contents
--------

.. toctree::
    :maxdepth: 2

    api
    contributing
    changelog


License
-------

Gimlet is licensed under an MIT license. Please see the LICENSE file for more
information.
