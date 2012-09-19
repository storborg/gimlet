class Crypter(object):
    recommended = ("The recommended method for generating the key is "
                   "os.urandom(32).encode('hex').")

    def __init__(self, key):
        from Crypto.Cipher import AES

        try:
            key = key.decode('hex')
        except TypeError:
            raise ValueError("Encryption key must be 64 hex digits (32 bytes"
                             "). " + self.recommended)

        if len(key) not in (16, 24, 32):
            raise ValueError("Encryption key must be 16, 24, or 32 bytes. " +
                             self.recommended)

        self.aes = AES.new(key, AES.MODE_ECB)

    def pad(self, cleartext):
        extra = 16 - (len(cleartext) % 16)
        cleartext += ('\0' * extra)
        return cleartext

    def unpad(self, cleartext):
        return cleartext.rstrip('\0')

    def encrypt(self, cleartext):
        return self.aes.encrypt(self.pad(cleartext))

    def decrypt(self, ciphertext):
        return self.unpad(self.aes.decrypt(ciphertext))
