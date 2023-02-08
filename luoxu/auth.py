import time
import secrets

class TokenManager:
    def __init__(self, ttl):
        self.tokens = {}
        self.ttl = ttl

    def add_token(self, gid):
        if gid in self.tokens and self.tokens[gid]["expiry"] > time.time():
            return self.tokens[gid]["token"]

        token = secrets.token_urlsafe(8)
        expiry_time = time.time() + self.ttl
        self.tokens[gid] = {"token": token, "expiry": expiry_time}

        return token


    def remove_expired_tokens(self):
        current_time = time.time()
        self.tokens = {gid: data for gid, data in self.tokens.items() if data["expiry"] > current_time}

    def is_valid(self, gid, token):
        self.remove_expired_tokens()
        token_data = self.tokens.get(gid)
        if token_data and token_data["token"] == token:
            return True
        return False
