"""Keep other documents in order, then append the three diagram groups."""
import re
import unicodedata
from pathlib import Path

DIAGRAMS = ('システム系統図', 'ケーブル系統図', '空中線系統図')

def key(path):
    name = unicodedata.normalize('NFKC', Path(path).name)
    category = next((i for i, prefix in enumerate(DIAGRAMS) if name.startswith(prefix)), None)
    if category is None:
        return None
    natural = tuple((0, int(part)) if part.isdigit() else (1, part.casefold())
                    for part in re.split(r'(\d+)', name))
    return category, natural

def order_diagrams(paths):
    return ([p for p in paths if key(p) is None]
            + sorted((p for p in paths if key(p) is not None), key=key))
