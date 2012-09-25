&#127864; Gimlet - Simple High-Performance WSGI Sessions
========================================================

Scott Torborg - [Cart Logic](http://www.cartlogic.com)

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
* &frac12; oz lime juice
* &frac14; simple syrup
* lime garnish

Limitations
===========

Currently NOT supported:

* Server-side expiration


Installation
============

    $ pip install gimlet


Quick Start
===========

### Basic Setup ###

Gimlet provides a WSGI Middleware which populates a Session object in the
WSGI environ. The most simple setup looks like:

    from gimlet import SessionMiddleware, RedisBackend

    backend = RedisBackend()

    app = SuperAwesomeApp()
    app = SessionMiddleware(app, 's3krit', backend)

Inside your app code, you can access the session like:

    session = environ['gimlet.session']
    session['user'] = 'Frodo'

The session data will automatically be persisted at the end of the request.

A unique identifier for the session (also visible to the client) is available
as ``session.id``.

### Key Options ###

Typical web applications tend to have a concentration of session access on a
relatively small set of keys, with small values. For example, a common session
variable may be a key referencing the logged-in user's account. Gimlet provides
fuctionality to store these commonly-accessed small keys on the clientside, in
the session cookie. This substantially reduces the I/O load of the application
as awhole, without limiting the session flexibility (particularly important for
adapting legacy apps).

To specify that a key should be stored on the client, pass the
``clientside=True`` argument:

    session.set('cart_id', 12345, clientside=True)

**SECURITY NOTE** Keys that are stored on the client side are not encrypted by
default, so it will be possible for eavesdroppers or end users to view their
contents. THey are signed, however, so they cannot be modified without
detection. To enable encryption of cookies, supply a random 64-char hex string
as the ``encryption_key`` argument to ``SessionMiddleware``.

Keys can also be set as secure or not, and within secure keys, permanent or
not. For example:

    session.set('account_id', 777, secure=True, permanent=False)

Or, combined:

    session.set('cart_id', 12345, clientside=True, secure=True)

### To Do ###

Features that may be coming soon:

- SQL backend.

Test areas that still need work:

- Setting defaults for key setting in the middleware configuration.


Code Standards
==============

Gimlet has a comprehensive test suite with 100% line and branch coverage, as
reported by the excellent ``coverage`` module. To run the tests, simply run in
the top level of the repo:

    $ nosetests

There are no [PEP8](http://www.python.org/dev/peps/pep-0008/) or
[Pyflakes](http://pypi.python.org/pypi/pyflakes) warnings in the codebase. To
verify that:

    $ pip install pep8 pyflakes
    $ pep8 .
    $ pyflakes .

Any pull requests must maintain the sanctity of these three pillars.
