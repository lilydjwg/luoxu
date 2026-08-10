from typing import NamedTuple, Optional
import datetime

class SearchQuery(NamedTuple):
  group: int
  terms: Optional[str]
  sender: Optional[str]
  start: Optional[datetime.datetime]
  end: Optional[datetime.datetime]
  token: Optional[str]

class GroupNotFound(Exception):
  def __init__(self, group):
    self.group = group

  def __str__(self):
    return f'no such group indexed: {self.group}'
