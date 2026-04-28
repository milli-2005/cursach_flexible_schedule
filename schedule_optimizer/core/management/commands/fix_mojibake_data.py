from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import CharField, TextField
import re


LATIN_MOJIBAKE_RE = re.compile(r'(?:Ð.|Ñ.){2,}')
CYRILLIC_MOJIBAKE_RE = re.compile(r'(?:Р.|С.){3,}')


def _has_non_russian_cyrillic(text: str) -> bool:
    for ch in text:
        o = ord(ch)
        if 0x0400 <= o <= 0x04FF and not ((0x0410 <= o <= 0x044F) or o in (0x0401, 0x0451)):
            return True
    return False


def _looks_mojibake(text: str) -> bool:
    if not text:
        return False
    if '�' in text:
        return True
    if LATIN_MOJIBAKE_RE.search(text):
        return True
    if CYRILLIC_MOJIBAKE_RE.search(text):
        marker_count = sum(1 for ch in text if ch in ('Р', 'С'))
        if marker_count >= 4 and marker_count / max(len(text), 1) > 0.2:
            return True
    if _has_non_russian_cyrillic(text):
        return True
    return False


def _decode_mojibake(value: str) -> str:
    # Fast path
    if not _looks_mojibake(value):
        return value

    candidates = [value]
    for enc in ('cp1251', 'latin1'):
        try:
            candidates.append(value.encode(enc).decode('utf-8'))
        except Exception:
            pass

    def score(s: str) -> tuple[int, int]:
        bad = 0
        for ch in s:
            o = ord(ch)
            if 0x0400 <= o <= 0x04FF and not ((0x0410 <= o <= 0x044F) or o in (0x0401, 0x0451)):
                bad += 1
        pair = len(LATIN_MOJIBAKE_RE.findall(s)) + len(CYRILLIC_MOJIBAKE_RE.findall(s))
        return (bad, pair)

    best = min(candidates, key=score)
    return best


class Command(BaseCommand):
    help = 'Fix mojibake in text fields across database records.'

    @transaction.atomic
    def handle(self, *args, **options):
        updated_rows = 0
        scanned_rows = 0

        for model in apps.get_models():
            text_fields = [
                f for f in model._meta.get_fields()
                if getattr(f, 'attname', None) and isinstance(f, (CharField, TextField))
            ]
            if not text_fields:
                continue

            qs = model.objects.all()
            for obj in qs.iterator(chunk_size=500):
                scanned_rows += 1
                changed = False

                for field in text_fields:
                    field_name = field.attname
                    value = getattr(obj, field_name, None)
                    if not isinstance(value, str) or not value:
                        continue

                    fixed = _decode_mojibake(value)
                    if fixed != value:
                        setattr(obj, field_name, fixed)
                        changed = True

                if changed:
                    obj.save(update_fields=[f.attname for f in text_fields])
                    updated_rows += 1

        self.stdout.write(self.style.SUCCESS(
            f'Done. Scanned records: {scanned_rows}. Updated records: {updated_rows}.'
        ))
