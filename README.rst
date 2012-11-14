Gimlet - Simple High-Performance WSGI Sessions
==============================================

Scott Torborg - `Cart Logic <http://www.cartlogic.com>`_

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


Installation
============

Install with pip::

    $ pip install gimlet


Documentation
=============

Gimlet has `extensive documentation here <http://www.cartlogic.com/gimlet>`_.


License
=======

Gimlet is licensed under an MIT license. Please see the LICENSE file for more
information.


Code Standards
==============

Gimlet has a comprehensive test suite with 100% line and branch coverage, as
reported by the excellent ``coverage`` module. To run the tests, simply run in
the top level of the repo::

    $ nosetests

There are no `PEP8 <http://www.python.org/dev/peps/pep-0008/>`_ or
`Pyflakes <http://pypi.python.org/pypi/pyflakes>`_ warnings in the codebase. To
verify that::

    $ pip install pep8 pyflakes
    $ pep8 .
    $ pyflakes .

Any pull requests must maintain the sanctity of these three pillars.
