#!/usr/bin/env python3
"""Convert mfqk.xml (MySQL XML dump) to SQLite database.

Single-pass streaming parser — processes structure+data as they appear.
"""

import sqlite3
import os
from xml.etree.ElementTree import iterparse

SRC = '/Users/xin/Downloads/mfqk.xml'
DST = '/Users/xin/Documents/Road_Of_Taixu/_data/mfqk/mfqk.db'


def mysql2sqlite(mysql_type):
    t = mysql_type.lower().split('(')[0]
    if t in ('int', 'tinyint', 'smallint', 'mediumint', 'bigint'):
        return 'INTEGER'
    elif t in ('float', 'double', 'decimal'):
        return 'REAL'
    else:
        return 'TEXT'


def build_create_sql(table_name, table_structure):
    fields = []
    pk_fields = []
    for child in table_structure:
        if child.tag == 'field':
            fname = child.attrib.get('Field')
            raw_type = child.attrib.get('Type')
            if not raw_type or not fname:
                continue
            ftype = mysql2sqlite(raw_type)
            fnull = '' if child.attrib.get('Null') == 'NO' else ''
            extra = child.attrib.get('Extra', '')
            is_pk = child.attrib.get('Key') == 'PRI'
            fields.append((fname, ftype, fnull, extra, is_pk))
            if is_pk:
                pk_fields.append(fname)

    cols = []
    for fname, ftype, fnull, extra, is_pk in fields:
        col = f'{fname} {ftype}'
        if fnull:
            col += f' {fnull}'
        # Single-column PK: mark AUTOINCREMENT inline. Composite PK handled below.
        if is_pk and len(pk_fields) == 1:
            col += ' PRIMARY KEY'
            if 'auto_increment' in extra.lower():
                col += ' AUTOINCREMENT'
        cols.append(col)

    # Composite primary key
    if len(pk_fields) > 1:
        cols.append(f'PRIMARY KEY ({", ".join(pk_fields)})')

    return f'CREATE TABLE IF NOT EXISTS [{table_name}] ({", ".join(cols)})'


def parse_row(row_elem):
    row = {}
    for field in row_elem:
        row[field.get('name')] = field.text or ''
    return row


def main():
    print(f'Source: {SRC}')
    print(f'Target: {DST}')

    # Remove existing db
    if os.path.exists(DST):
        os.remove(DST)

    conn = sqlite3.connect(DST)
    conn.execute('PRAGMA journal_mode=OFF')
    conn.execute('PRAGMA synchronous=OFF')
    cursor = conn.cursor()

    current_table = None
    batch = []
    BATCH_SIZE = 5000
    total_rows = 0
    table_counts = {}
    tables_created = []

    print('Processing...')

    for event, elem in iterparse(SRC, events=('start', 'end')):
        tag = elem.tag

        if tag == 'table_structure' and event == 'end':
            name = elem.get('name')
            sql = build_create_sql(name, elem)
            cursor.execute(sql)
            tables_created.append(name)

        elif tag == 'table_data':
            if event == 'start':
                # Switch target table BEFORE rows arrive
                current_table = elem.get('name')
                table_counts[current_table] = table_counts.get(current_table, 0)
            else:  # end
                # Flush remaining batch for this table
                if batch and current_table:
                    cols = list(batch[0].keys())
                    ph = ', '.join(['?'] * len(cols))
                    cursor.executemany(
                        f'INSERT INTO [{current_table}] ({", ".join(cols)}) VALUES ({ph})',
                        [tuple(r[c] for c in cols) for r in batch]
                    )
                    batch = []

        elif tag == 'row' and event == 'end' and current_table:
            row = parse_row(elem)
            batch.append(row)
            table_counts[current_table] += 1
            total_rows += 1

            if len(batch) >= BATCH_SIZE:
                cols = list(batch[0].keys())
                ph = ', '.join(['?'] * len(cols))
                cursor.executemany(
                    f'INSERT INTO [{current_table}] ({", ".join(cols)}) VALUES ({ph})',
                    [tuple(r[c] for c in cols) for r in batch]
                )
                batch = []

            if total_rows % 100000 == 0:
                conn.commit()
                print(f'  {total_rows} rows...', flush=True)

        # Free memory (don't clear children of table_structure — they're
        # yielded by iterparse before their parent and we need them intact)
        if event == 'end' and tag not in ('field', 'key', 'options'):
            elem.clear()

    # Final flush
    if batch and current_table:
        cols = list(batch[0].keys())
        ph = ', '.join(['?'] * len(cols))
        cursor.executemany(
            f'INSERT INTO [{current_table}] ({", ".join(cols)}) VALUES ({ph})',
            [tuple(r[c] for c in cols) for r in batch]
        )

    conn.commit()
    conn.close()

    size_mb = os.path.getsize(DST) / (1024 * 1024)
    print(f'\nTables created: {len(tables_created)}')
    for t in tables_created:
        print(f'  {t}: {table_counts.get(t, 0):,} rows')
    print(f'Total rows: {total_rows:,}')
    print(f'Database: {DST} ({size_mb:.1f} MB)')


if __name__ == '__main__':
    main()
