#!/usr/bin/env python3
"""
Build NT1904.SQLite3 — Nestle 1904 Greek New Testament in MyBible format.

Source: github.com/biblicalhumanities/Nestle1904 (CC BY-SA 4.0)
        XML markup: Jonathan Robie; base text: Diego Renato dos Santos.
Output: mobile/scripts/output/NT1904.SQLite3

Run from the project root:
    cd ministry-manager && python mobile/scripts/build_nestle1904.py
"""

import re
import sqlite3
from pathlib import Path
from urllib.request import urlopen

OUTPUT_DIR = Path(__file__).parent / 'output'
BASE_RAW   = 'https://raw.githubusercontent.com/biblicalhumanities/Nestle1904/master/xml/'

# (short_name, long_name, filename, mybible_num, sort_order, color)
# Names and colors match the WEB.SQLite3 books table for consistency
BOOKS = [
    ('Mt',   'The Gospel According to MATTHEW',                               '01-matthew.xml',        470, 40, '#ff6600'),
    ('Mr',   'The Gospel According to MARK',                                  '02-mark.xml',           480, 41, '#ff6600'),
    ('Lu',   'The Gospel According to LUKE',                                  '03-luke.xml',           490, 42, '#ff6600'),
    ('Joh',  'The Gospel According to JOHN',                                  '04-john.xml',           500, 43, '#ff6600'),
    ('Ac',   'THE ACTS of the Apostles',                                      '05-acts.xml',           510, 44, '#00ffff'),
    ('Ro',   'The Epistle of Paul the Apostle to the ROMANS',                 '06-romans.xml',         520, 45, '#ffff00'),
    ('1Co',  'The First Epistle of Paul the Apostle to the CORINTHIANS',      '07-1corinthians.xml',   530, 46, '#ffff00'),
    ('2Co',  'The Second Epistle of Paul the Apostle to the CORINTHIANS',     '08-2corinthians.xml',   540, 47, '#ffff00'),
    ('Ga',   'The Epistle of Paul the Apostle to the GALATIANS',              '09-galatians.xml',      550, 48, '#ffff00'),
    ('Eph',  'The Epistle of Paul the Apostle to the EPHESIANS',              '10-ephesians.xml',      560, 49, '#ffff00'),
    ('Php',  'The Epistle of Paul the Apostle to the PHILIPPIANS',            '11-philippians.xml',    570, 50, '#ffff00'),
    ('Col',  'The Epistle of Paul the Apostle to the COLOSSIANS',             '12-colossians.xml',     580, 51, '#ffff00'),
    ('1Th',  'The First Epistle of Paul the Apostle to the THESSALONIANS',    '13-1thessalonians.xml', 590, 52, '#ffff00'),
    ('2Th',  'The Second Epistle of Paul the Apostle to the THESSALONIANS',   '14-2thessalonians.xml', 600, 53, '#ffff00'),
    ('1Ti',  'The First Epistle of Paul the Apostle to TIMOTHY',              '15-1timothy.xml',       610, 54, '#ffff00'),
    ('2Ti',  'The Second Epistle of Paul the Apostle to TIMOTHY',             '16-2timothy.xml',       620, 55, '#ffff00'),
    ('Tit',  'The Epistle of Paul the Apostle to TITUS',                      '17-titus.xml',          630, 56, '#ffff00'),
    ('Phm',  'The Epistle of Paul the Apostle to PHILEMON',                   '18-philemon.xml',       640, 57, '#ffff00'),
    ('Heb',  'The Epistle to the HEBREWS',                                    '19-hebrews.xml',        650, 58, '#ffff00'),
    ('Jas',  'The Epistle of JAMES',                                          '20-james.xml',          660, 59, '#00ff00'),
    ('1Pe',  'The First Epistle of PETER',                                    '21-1peter.xml',         670, 60, '#00ff00'),
    ('2Pe',  'The Second Epistle of PETER',                                   '22-2peter.xml',         680, 61, '#00ff00'),
    ('1Jo',  'The First Epistle of JOHN',                                     '23-1john.xml',          690, 62, '#00ff00'),
    ('2Jn',  'The Second Epistle of JOHN',                                    '24-2john.xml',          700, 63, '#00ff00'),
    ('3Jo',  'The Third Epistle of JOHN',                                     '25-3john.xml',          710, 64, '#00ff00'),
    ('Jude', 'The Epistle of JUDE',                                           '26-jude.xml',           720, 65, '#00ff00'),
    ('Rev',  'THE REVELATION of Jesus Christ',                                '27-revelation.xml',     730, 66, '#ff7c80'),
]

# Matches any OSIS milestone element
MILESTONE_RE = re.compile(r'<milestone\b[^>]*/>')
# Matches <w> (word) and <pc> (punctuation) tokens in document order
TOKEN_RE     = re.compile(r'<(w|pc)(?:\s[^>]*)?>([^<]*)</(w|pc)>')


def fetch_xml(filename: str) -> str:
    url = BASE_RAW + filename
    print(f'    GET {url}')
    with urlopen(url, timeout=90) as r:
        return r.read().decode('utf-8', errors='replace')


def get_verse_ref(tag: str):
    """Return (chapter, verse) if tag is a verse milestone, else None."""
    if 'unit="verse"' not in tag:
        return None
    m = re.search(r'\bid="([^"]+)"', tag)
    if not m:
        return None
    parts = m.group(1).split('.')
    if len(parts) == 3:
        try:
            return int(parts[1]), int(parts[2])
        except ValueError:
            pass
    return None


def build_verse_text(chunk: str) -> str:
    """
    Collect <w> and <pc> tokens from an XML fragment and join into a verse string.
    Punctuation (<pc>) is attached to the preceding word without a space.
    """
    tokens: list = []
    for m in TOKEN_RE.finditer(chunk):
        tag, text = m.group(1), m.group(2)
        if not text:
            continue
        if tag == 'pc':
            if tokens:
                tokens[-1] += text   # attach punctuation directly to preceding word
        else:
            tokens.append(text)
    return ' '.join(tokens)


def parse_book(xml_text: str, book_num: int) -> list:
    """Parse all verse milestones in the book XML, return (book_num, ch, vs, text) rows."""
    # Collect (match_start, match_end, tag_text) for every milestone element
    milestones = [(m.start(), m.end(), m.group(0)) for m in MILESTONE_RE.finditer(xml_text)]

    # Keep only verse milestones
    verse_milestones = []
    for start, end, tag in milestones:
        ref = get_verse_ref(tag)
        if ref:
            verse_milestones.append((start, end, ref))

    verses = []
    for i, (_ms, me, (ch, vs)) in enumerate(verse_milestones):
        # Content runs from after this milestone to the start of the next milestone
        content_end = verse_milestones[i + 1][0] if i + 1 < len(verse_milestones) else len(xml_text)
        text = build_verse_text(xml_text[me:content_end])
        if text:
            verses.append((book_num, ch, vs, text))
    return verses


def build():
    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / 'NT1904.SQLite3'
    if out.exists():
        out.unlink()

    all_verses: list = []
    book_rows:  list = []

    for short, long_name, filename, num, sort, color in BOOKS:
        print(f'\n{short}:')
        xml_text = fetch_xml(filename)
        verses   = parse_book(xml_text, num)
        print(f'  {len(verses)} verses parsed')
        all_verses.extend(verses)
        book_rows.append((num, short, long_name, color, sort))

    print(f'\nTotal: {len(all_verses):,} verses across {len(BOOKS)} books')

    conn = sqlite3.connect(out)
    c    = conn.cursor()

    c.execute('''CREATE TABLE books (
        book_number   NUMERIC NOT NULL PRIMARY KEY,
        short_name    TEXT    NOT NULL,
        long_name     TEXT    NOT NULL,
        book_color    TEXT    NOT NULL,
        sorting_order NUMERIC NOT NULL DEFAULT 0
    )''')
    c.executemany('INSERT INTO books VALUES (?,?,?,?,?)', book_rows)

    c.execute('''CREATE TABLE verses (
        book_number NUMERIC NOT NULL,
        chapter     NUMERIC NOT NULL,
        verse       NUMERIC NOT NULL,
        text        TEXT    NOT NULL DEFAULT '',
        PRIMARY KEY (book_number, chapter, verse)
    )''')
    c.executemany('INSERT INTO verses VALUES (?,?,?,?)', all_verses)

    c.execute('''CREATE TABLE stories (
        book_number      NUMERIC NOT NULL,
        chapter          NUMERIC NOT NULL,
        verse            NUMERIC NOT NULL,
        order_if_several NUMERIC NOT NULL DEFAULT 0,
        title            TEXT    NOT NULL DEFAULT '',
        PRIMARY KEY (book_number, chapter, verse, order_if_several)
    )''')

    c.execute('CREATE TABLE info (name TEXT NOT NULL, value TEXT)')
    c.executemany('INSERT INTO info VALUES (?,?)', [
        ('description',   'Nestle 1904 Greek New Testament (NT only)'),
        ('language',      'grc'),
        ('detailed_info', 'Nestle 1904 GNT. XML markup by Jonathan Robie, CC BY-SA 4.0. '
                          'Base text by Diego Renato dos Santos. '
                          'Source: github.com/biblicalhumanities/Nestle1904'),
        ('is_strong',     'false'),
        ('is_footnotes',  'false'),
    ])

    conn.commit()
    total = c.execute('SELECT COUNT(*) FROM verses').fetchone()[0]
    size  = out.stat().st_size
    conn.close()
    print(f'\nWritten {total:,} verses to {out}  ({size:,} bytes)')


if __name__ == '__main__':
    build()
