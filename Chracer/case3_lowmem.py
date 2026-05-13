#!/usr/bin/env python3
import argparse
import datetime
import gc
import sys
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

from lowmem_runtime import configure_lowmem_symbols, save_results

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case3.dmp'
DEFAULT_BASES = [1885639781552]


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case3.')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=DEFAULT_BASES)
    return p.parse_args()


def main():
    args = parse_args()

    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab, NavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
        try:
            browser = Browser(mdmp, base)
            session_id = browser.session_id

            tabs = browser.tab_strip_model.contents_data.entries
            for tab_idx, tab_base in enumerate(tabs):
                tab_base = int.from_bytes(tab_base, 'little')
                tab = Tab(mdmp, tab_base)

                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                for nav_entry_base in nav_entries:
                    nav_entry_base = int.from_bytes(nav_entry_base, 'little')
                    nav_entry = NavigationEntry(mdmp, nav_entry_base)
                    frame_entry = nav_entry.frame_tree.frame_entry
                    rows.append((
                        session_id,
                        tab_idx,
                        nav_entry.timestamp.to_datetime(),
                        frame_entry.url,
                        frame_entry.referrer.url,
                    ))
                gc.collect()
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    headers = ['SessionID', 'Tab', 'Time', 'URL', 'Referrer']
    table_output, txt_path, csv_path = save_results(ROOT, 'case3_lowmem', headers, rows)
    print(table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()
