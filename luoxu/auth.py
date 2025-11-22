import secrets
import hashlib
import hmac
import time

from .lib.expiringdict import ExpiringDict

class TokenManager:
    def __init__(self, ttl):
        self._token_dict = ExpiringDict(default_ttl=ttl)

    def add_token(self, group_id):
        self._token_dict.expire()
        if existing_token := self._token_dict.get(group_id):
            return existing_token
        new_token = secrets.token_urlsafe(8)
        self._token_dict[group_id] = new_token
        return new_token

    def is_valid(self, group_id, token):
        self._token_dict.expire()
        if not (existing_token := self._token_dict.get(group_id)):
            return False
        # hmac.compare_digest?
        return existing_token == token

def Verify_telegram_oauth(bot_token, data:dict):
    hash_str = ""
    text_list = []
    for key, value in data.items():
        if key == "hash":
            hash_str = value
        else:
            text_list.append(f"{key}={value}")
    check_str = "\n".join(sorted(text_list))
    try:
        if time.time() - int(data['auth_date']) > 86400:
            return None
    except ValueError:
        return None

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hmac_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    # hmac.compare_digest?
    if not (hmac_hash == hash_str):
        return None
    return data['id']
