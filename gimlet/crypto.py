class Crypter(object):

    def __init__(self, key):
        from Crypto.Cipher import AES

        if len(key) not in (16, 24, 32):
            raise ValueError("Encryption key must be 16, 24, or 32 bytes. The "
                             "recommended method for generating the key is "
                             "'os.unrandom(32)'")

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
