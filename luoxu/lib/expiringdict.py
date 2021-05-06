from collections import UserDict
import time

class ExpiringDict(UserDict):
  def __init__(self, expiration, maxsize=100):
    super().__init__()
    self.expiration = expiration
    self.maxsize = maxsize

  def __getitem__(self, key):
    item, t = self.data[key]
    return item

  def __setitem__(self, key, value):
    t = time.time()
    self.data[key] = value, t

  def __delitem__(self, key):
    del self.data[key]

  def expire(self):
    deadline = time.time() - self.expiration
    expired_keys = [k for k, (_, t) in self.data.items() if t < deadline]
    for k in expired_keys:
      del self.data[k]

    if len(self.data) > self.maxsize:
      keys = [k for k, _ in sorted(self.data.items(), key=lambda x: x[1][1])]
      overflowed = keys[-self.maxsize:]
      for k in overflowed:
        del self.data[k]
