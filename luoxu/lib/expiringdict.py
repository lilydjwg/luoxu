from collections import UserDict
import time

class ExpiringDict(UserDict):
  def __init__(self, default_ttl, maxsize=100):
    super().__init__()
    self.default_ttl = default_ttl
    self.maxsize = maxsize

  def __getitem__(self, key):
    item, t = self.data[key]
    return item

  def __setitem__(self, key, value):
    self.set_item(key, value)

  def set_item(self, key, value, ttl=None):
    if ttl is None:
      ttl = self.default_ttl
    t = time.time() + ttl
    self.data[key] = value, t

  def __delitem__(self, key):
    del self.data[key]

  def expire(self):
    now = time.time()
    expired_keys = [k for k, (_, t) in self.data.items() if t < now]
    for k in expired_keys:
      del self.data[k]

    if len(self.data) > self.maxsize:
      keys = [k for k, _ in sorted(self.data.items(), key=lambda x: x[1][1])]
      overflowed = keys[-self.maxsize:]
      for k in overflowed:
        del self.data[k]
