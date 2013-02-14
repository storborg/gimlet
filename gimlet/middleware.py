from webob import Request

from .factories import session_factory_factory


class SessionMiddleware(object):

    def __init__(self, app, secret, environ_key='gimlet.session',
                 *args, **kwargs):
        self.app = app
        self.environ_key = environ_key
        self.session_factory = session_factory_factory(secret, *args, **kwargs)

    def __call__(self, environ, start_response):
        req = Request(environ)
        sess = self.session_factory(req)
        req.environ[self.environ_key] = sess
        resp = req.get_response(self.app)
        sess.response_callback(req, resp)
        return resp(environ, start_response)
