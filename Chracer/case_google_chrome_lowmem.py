#!/usr/bin/env python3
import argparse
import datetime
import sys
from pathlib import Path

import tqdm
from minidump.minidumpfile import MinidumpFile
from minidump.streams import MemoryType, MemoryState, AllocationProtect

from lowmem_runtime import configure_lowmem_symbols, save_results

ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case_google_chrome.dmp'


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case_google_chrome.')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=[])
    return p.parse_args()


def main():
    args = parse_args()

    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chrome.chrome import ChromeBrowser, ChromeTab, ChromeNavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to find Browser objects at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)

    browser_instances = []
    if args.bases:
        for base in args.bases:
            b = ChromeBrowser(mdmp, base)
            if b.validate():
                browser_instances.append(b)
    else:
        for m in tqdm.tqdm(mdmp.memory_info.infos):
            if m.Type == MemoryType.MEM_PRIVATE and m.State == MemoryState.MEM_COMMIT and m.Protect == AllocationProtect.PAGE_READWRITE:
                end = m.BaseAddress + m.RegionSize - ChromeBrowser.instance_size()
                for addr in range(m.BaseAddress, end, 8):
                    b = ChromeBrowser(mdmp, addr)
                    if not b.validate():
                        continue
                    tabs = b.tab_strip_model.contents_data.entries
                    tab = ChromeTab(mdmp, int.from_bytes(tabs[0], 'little'))
                    if not tab.validate():
                        continue
                    entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                    entry = ChromeNavigationEntry(mdmp, int.from_bytes(entries[0], 'little'))
                    if not entry.validate():
                        continue
                    browser_instances.append(b)

    print('### end to find Browser objects at', datetime.datetime.now())
    print('### start to extract information at', datetime.datetime.now())

    rows = []
    for b in browser_instances:
        for ti, tp in enumerate(b.tab_strip_model.contents_data.entries):
            t = ChromeTab(mdmp, int.from_bytes(tp, 'little'))
            nc = t.contents.primary_frame_tree.navigator.controller
            for ep in nc.entries.entries:
                e = ChromeNavigationEntry(mdmp, int.from_bytes(ep, 'little'))
                fe = e.frame_tree.frame_entry
                rows.append((b.session_id, ti, e.timestamp.to_datetime(), e.title.string, fe.url.spec.string))

    print('### end to extract information at', datetime.datetime.now())
    headers = ['SessionID', 'Tab', 'Time', 'Title', 'URL']
    table_output, txt_path, csv_path = save_results(ROOT, 'case_google_chrome_lowmem', headers, rows)
    print(table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()
