import cPickle as pickle

from struct import Struct

from itsdangerous import Serializer, URLSafeSerializerMixin


class CookieSerializer(Serializer):
    packer = Struct('16si')

    def __init__(self, secret, backend, crypter):
        Serializer.__init__(self, secret)
        self.backend = backend
        self.crypter = crypter

    def load_payload(self, payload):
        """
        Convert a cookie into a SessionChannel instance.
        """
        if self.crypter:
            payload = self.crypter.decrypt(payload)

        raw_id, created_timestamp = \
            self.packer.unpack(payload[:self.packer.size])
        client_data_pkl = payload[self.packer.size:]

        id = raw_id.encode('hex')
        client_data = pickle.loads(client_data_pkl)
        return id, created_timestamp, client_data

    def dump_payload(self, channel):
        """
        Convert a Session instance into a cookie by packing it precisely into a
        string.
        """
        client_data_pkl = pickle.dumps(channel.client_data)
        raw_id = channel.id.decode('hex')
        payload = (self.packer.pack(raw_id, channel.created_timestamp) +
                   client_data_pkl)

        if self.crypter:
            payload = self.crypter.encrypt(payload)

        return payload


class URLSafeCookieSerializer(URLSafeSerializerMixin, CookieSerializer):
    pass
