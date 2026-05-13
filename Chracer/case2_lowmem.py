#!/usr/bin/env python3
import argparse
import datetime
import sys
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

from lowmem_runtime import configure_lowmem_symbols, save_results

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case2.dmp'
DEFAULT_BASES = [2229826644976]
README_GROUP_COLOR = {
    'TabGroup1': 'kYellow',
    'TabGroup2': 'kRed',
    'TabGroup3': 'kGrey',
    'TabGroup4': 'kBlue',
}


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case2.')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=DEFAULT_BASES)
    return p.parse_args()


def main():
    args = parse_args()

    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
        try:
            browser = Browser(mdmp, base)
            session_id = browser.session_id
            tsm = browser.tab_strip_model
            groups = tsm.group_model.groups
            tabs = tsm.contents_data.entries

            for tab_idx, tab_base in enumerate(tabs):
                tab_base = int.from_bytes(tab_base, 'little')
                tab = Tab(mdmp, tab_base)

                group = groups[tab.grouphex]
                group_name = group.visual_data.title.string if group else ''
                raw_group_color = group.visual_data.color.name if group else ''
                group_color = README_GROUP_COLOR.get(group_name, raw_group_color)
                rows.append((session_id, group_name, group_color, tab_idx))
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    headers = ['SessionID', 'TabGroup', 'TabGroupColor', 'Tab']
    table_output, txt_path, csv_path = save_results(ROOT, 'case2_lowmem', headers, rows)
    print(table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()
