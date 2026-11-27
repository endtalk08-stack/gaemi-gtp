"""Sentence endings to 해요체 for broadcast reading, by fixed rules (no AI).

"증가했다." / "증가했습니다." -> "증가했어요."   "있다" -> "있어요"   "된다" -> "돼요"
"수치이다" / "수치입니다" -> "수치예요"(no final consonant) / "이에요"(final consonant)
Only sentence-final words change; anything not in the rules is left as it is.
"""
import re

END = r"(?=[.!?…\"'”’)\]]*(?:\s|$))"


def _batchim(ch):
    code = ord(ch) - 0xAC00
    return 0 <= code <= 11171 and code % 28 != 0


def _jong(ch):
    code = ord(ch) - 0xAC00
    return code % 28 if 0 <= code <= 11171 else -1


DIGIT_BATCHIM = set("013678")     # 영 일 삼 육 칠 팔 end in a consonant


def _copula(match):
    before = match.group(1)
    final = _batchim(before) or before in DIGIT_BATCHIM
    return before + ("이에요" if final else "예요")


RULES = [
    (re.compile(r"것이다" + END), "거예요"),
    (re.compile(r"것입니다" + END), "거예요"),
    (re.compile(r"([가-힣0-9%)])(?:입니다|이다)" + END), _copula),
    (re.compile(r"(?:합니다|한다)" + END), "해요"),
    (re.compile(r"(?:됩니다|된다)" + END), "돼요"),
    (re.compile(r"없(?:습니다|다)" + END), "없어요"),
    # Any syllable ending in ㅆ (했/됐/였/었/았/있/겠…) + 다 / 습니다 -> + 어요
    (re.compile(r"([가-힣])(?:습니다|다)" + END),
     lambda m: m.group(1) + "어요" if _jong(m.group(1)) == 20 else m.group(0)),
]


def haeyo(text):
    if not isinstance(text, str) or not text:
        return text
    for pattern, repl in RULES:
        text = pattern.sub(repl, text)
    return text


def subject(name):
    """엔비디아 -> 엔비디아가, 마이크론 -> 마이크론이 (가 for names not ending in Hangul)."""
    name = str(name or "").strip()
    return name + ("이" if name and _batchim(name[-1]) else "가")
