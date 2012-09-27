import cPickle as pickle


class BaseBackend(object):

    def __init__(self, prefix='gimlet.'):
        self.prefix = prefix

    def prefixed_key(self, key):
        return self.prefix + key

    def serialize(self, value):
        return pickle.dumps(value)

    def deserialize(self, raw):
        return pickle.loads(raw)
