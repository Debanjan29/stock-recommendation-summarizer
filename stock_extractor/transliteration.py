"""
Transliteration and Hindi script sanitization module.
Ensures that no report is generated in pure Devanagari Hindi script.
Converts any Devanagari text into readable Hinglish (Latin/Roman script).
"""

import re
from typing import Optional, Any

DEVA_TO_ROMAN = {
    # Independent Vowels
    'अ': 'a', 'आ': 'aa', 'इ': 'i', 'ई': 'ee', 'उ': 'u', 'ऊ': 'oo', 'ऋ': 'ri',
    'ए': 'e', 'ऐ': 'ai', 'ओ': 'o', 'औ': 'au', 'अं': 'an', 'अः': 'ah',
    # Nukta consonants
    'क़': 'q', 'ख़': 'kh', 'ग़': 'gh', 'ज़': 'z', 'ड़': 'd', 'ढ़': 'dh', 'फ़': 'f',
    # Consonants
    'क': 'k', 'ख': 'kh', 'ग': 'g', 'घ': 'gh', 'ङ': 'ng',
    'च': 'ch', 'छ': 'chh', 'ज': 'j', 'झ': 'jh', 'ञ': 'ny',
    'ट': 't', 'ठ': 'th', 'ड': 'd', 'ढ': 'dh', 'ण': 'n',
    'त': 't', 'थ': 'th', 'द': 'd', 'ध': 'dh', 'न': 'n',
    'प': 'p', 'फ': 'ph', 'ब': 'b', 'भ': 'bh', 'म': 'm',
    'य': 'y', 'र': 'r', 'ल': 'l', 'व': 'v', 'श': 'sh', 'ष': 'sh', 'स': 's', 'ह': 'h',
    'ळ': 'l', 'क्ष': 'ksh', 'त्र': 'tr', 'ज्ञ': 'gya', 'श्र': 'shra',
    # Matras (dependent vowel signs)
    'ा': 'aa', 'ि': 'i', 'ी': 'ee', 'ु': 'u', 'ू': 'oo', 'ृ': 'ri',
    'े': 'e', 'ै': 'ai', 'ो': 'o', 'ौ': 'au', 'ॉ': 'o', 'ॅ': 'e',
    # Modifiers
    'ं': 'n', 'ँ': 'n', 'ः': 'h', '्': '',
    # Digits
    '०': '0', '१': '1', '२': '2', '३': '3', '४': '4',
    '५': '5', '६': '6', '७': '7', '८': '8', '९': '9',
    '।': '.', '॥': '.'
}

CONSONANTS = set('कखगघङचछजझञटठडढणतथदधनपफबभमयरलवशषसहळ')
MATRAS = set('ािीुूृेैोौॉॅ')

def has_devanagari(text: Optional[str]) -> bool:
    """Check if string contains any Devanagari characters."""
    if not text:
        return False
    return bool(re.search(r'[\u0900-\u097F]', str(text)))

def devanagari_to_hinglish(text: Optional[str]) -> str:
    """
    Transliterate Devanagari Hindi text to readable Hinglish (Roman alphabet).
    Preserves existing English, punctuation, and ASCII text.
    """
    if not text or not has_devanagari(text):
        return text or ""

    clean_text = str(text)
    clean_text = (clean_text.replace('क़', 'q').replace('ख़', 'kh').replace('ग़', 'gh')
                  .replace('ज़', 'z').replace('ड़', 'd').replace('ढ़', 'dh').replace('फ़', 'f'))

    res = []
    chars = list(clean_text)
    n = len(chars)
    i = 0
    while i < n:
        c = chars[i]
        next_c = chars[i+1] if i + 1 < n else None

        if c in CONSONANTS:
            base = DEVA_TO_ROMAN.get(c, c)
            if next_c in MATRAS:
                res.append(base)
                res.append(DEVA_TO_ROMAN.get(next_c, ''))
                i += 2
                continue
            elif next_c == '्':
                res.append(base)
                i += 2
                continue
            elif next_c in CONSONANTS or (next_c and ord(next_c) >= 0x0900 and ord(next_c) <= 0x097F and next_c not in ' \t\n\r,.;:!?।#'):
                res.append(base + 'a')
                i += 1
                continue
            else:
                res.append(base)
                i += 1
                continue
        elif c in DEVA_TO_ROMAN:
            res.append(DEVA_TO_ROMAN[c])
            i += 1
        else:
            res.append(c)
            i += 1

    return "".join(res)

def ensure_no_pure_hindi(text: Optional[str]) -> str:
    """
    Ensure the provided text has NO pure Devanagari Hindi characters.
    If Devanagari is present, transliterates to Hinglish (Roman English script).
    """
    if not text:
        return ""
    if has_devanagari(text):
        return devanagari_to_hinglish(text)
    return str(text)
