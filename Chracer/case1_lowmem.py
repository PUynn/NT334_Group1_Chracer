#!/usr/bin/env python3
import argparse
import datetime
import gc
import sys
from pathlib import Path

from tabulate import tabulate
from minidump.minidumpfile import MinidumpFile

from lowmem_runtime import configure_lowmem_symbols

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case1.dmp'
RESULT_DIR = ROOT / 'result'


def extract_case1(dump_path, browser_bases):
    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()

    configure_lowmem_symbols(ROOT)

    from chracer.chromium import Browser
    from chracer.tab import Tab, NavigationEntry

    print('### end to load symbols at', datetime.datetime.now())
    print('### start to extract information at', datetime.datetime.now())
    sys.stdout.flush()

    mdmp = MinidumpFile.parse(str(dump_path))
    printed_table = []

    for base in browser_bases:
        print('### processing Browser base 0x{:X}'.format(base))
        sys.stdout.flush()
        try:
            browser = Browser(mdmp, base)
            session_id = browser.session_id
        except Exception as e:
            print('[WARN] 0x{:X} is not a Browser object ({})'.format(base, e))
            continue

        try:
            tabs = browser.tab_strip_model.contents_data.entries
        except Exception as e:
            print('[WARN] Browser 0x{:X} tab list error ({})'.format(base, e))
            continue

        for tab_idx, tab_base_raw in enumerate(tabs):
            tab_base = int.from_bytes(tab_base_raw, 'little')
            try:
                tab = Tab(mdmp, tab_base)
                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
            except Exception as e:
                print('[WARN] 0x{:X} tab/nav error ({})'.format(tab_base, e))
                continue

            for nav_entry_base_raw in nav_entries:
                nav_entry_base = int.from_bytes(nav_entry_base_raw, 'little')
                try:
                    nav_entry = NavigationEntry(mdmp, nav_entry_base)
                    title = nav_entry.title.string
                    url = nav_entry.frame_tree.frame_entry.url
                    printed_table.append((session_id, tab_idx, title, url))
                except Exception as e:
                    print('[WARN] 0x{:X} nav entry error ({})'.format(nav_entry_base, e))
                    continue

            gc.collect()

    print('### end to extract information at', datetime.datetime.now())
    table_output = tabulate(printed_table, headers=['SessionID', 'Tab', 'Title', 'URL'])
    print(table_output)

    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    txt_path = RESULT_DIR / f'case1_lowmem_{ts}.txt'
    csv_path = RESULT_DIR / f'case1_lowmem_{ts}.csv'

    txt_path.write_text(table_output + '\n', encoding='utf-8')
    with csv_path.open('w', encoding='utf-8', newline='') as f:
        f.write('SessionID,Tab,Title,URL\n')
        for session_id, tab_idx, title, url in printed_table:
            safe_title = '"' + str(title).replace('"', '""') + '"'
            safe_url = '"' + str(url).replace('"', '""') + '"'
            f.write(f'{session_id},{tab_idx},{safe_title},{safe_url}\n')

    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


def parse_args():
    parser = argparse.ArgumentParser(description='Low-memory case1 extractor (does not modify case1.py).')
    parser.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to .dmp file')
    parser.add_argument(
        '--bases',
        nargs='*',
        type=lambda x: int(x, 0),
        default=[2097297655728, 2097301836336, 2097349779280, 2097419539712],
        help='Browser object addresses (decimal or 0x...)',
    )
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    extract_case1(Path(args.dump), args.bases)
