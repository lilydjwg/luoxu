import secrets
import hashlib
import hmac
import time
import json
import base64

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

def Verify_telegram_oauth(bot_token, auth_str):
    padding = '=' * (4 - len(auth_str) % 4)
    auth_str += padding
    try:
      data = json.loads(base64.urlsafe_b64decode(auth_str).decode('utf-8'))
    except:
      return None
    hash_str = ""
    text_list = []
    for key, value in data.items():
        if key == "hash":
            hash_str = value
        else:
            text_list.append(f"{key}={value}")
    check_str = "\n".join(sorted(text_list))
    try:
        if time.time() - int(data['auth_date']) > 60 * 60 * 24 * 30:
            return None
    except (ValueError, KeyError, TypeError):
        return None

    secret_key = hashlib.sha256(bot_token.encode()).digest()
    hmac_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
    # hmac.compare_digest?
    if hmac_hash != hash_str:
      return None
    return data['id']
