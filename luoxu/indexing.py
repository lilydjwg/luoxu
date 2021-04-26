import regex

from opencc import OpenCC

CONVERTERS = [
  OpenCC('s2tw'),
  OpenCC('tw2s'),
  OpenCC('s2twp'),
  OpenCC('tw2sp'),
]

def text_to_vector(s):
  s = s.lower()
  s = regex.sub(r'(\p{Han})', r' \1 ', s)
  s = regex.sub(r'[\W_]', ' ', s)
  s = regex.sub(r'\s+', ' ', s)
  return s.strip()

def text_to_query(s):
  # TODO: support A OR B and -A
  s = s.lower()
  s = regex.sub(r'[\W_]', ' ', s)

  variants = {c.convert(s) for c in CONVERTERS}
  if len(variants) > 1:
    s = ' OR '.join(variants)
  else:
    s = variants.pop()

  s = regex.sub(r'(\p{Han})', r' \1 ', s)
  s = regex.sub(r'\s+', ' ', s)
  return s
