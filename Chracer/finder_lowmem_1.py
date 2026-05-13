#!/usr/bin/env python3
import argparse
import datetime
import gc
import os
import sys
import tqdm
from pathlib import Path

from minidump.minidumpfile import MinidumpFile
from lowmem_runtime import configure_lowmem_symbols, save_results
# IMPORT MODULE BẢO TOÀN CHỨNG CỨ
from acquisition.hash_dump import preserve_evidence
ROOT = Path(__file__).resolve().parent

def parse_args():
    p = argparse.ArgumentParser(description='Low-memory finder for unknown dump (Base version).')
    p.add_argument('dump', help='Path to dump file')
    return p.parse_args()


def main():
    args = parse_args()
    dump_file = args.dump
    preserve_evidence(dump_file)

    if not os.path.exists(dump_file):
        print(f'Lỗi: File {dump_file} không tồn tại.')
        sys.exit(1)

    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    
    from chracer.chromium import Browser, Tab, NavigationEntry, MemoryType, MemoryState, AllocationProtect
    print('### end to load symbols at', datetime.datetime.now())

    print('[NOTICE] The program is very slow because it hasn\'t been optimized yet.')
    print('### start to find Browser objects at', datetime.datetime.now())

    mdmp = MinidumpFile.parse(dump_file)
    browser_bases = []

    for m in tqdm.tqdm(mdmp.memory_info.infos):
        if m.Type == MemoryType.MEM_PRIVATE \
        and m.State == MemoryState.MEM_COMMIT \
        and m.Protect == AllocationProtect.PAGE_READWRITE:
            
            for addr in range(m.BaseAddress, m.BaseAddress + m.RegionSize - Browser.instance_size(), 8):
                try:
                    b = Browser(mdmp, addr)
                    if not b.validate(): continue

                    tabs = b.tab_strip_model.contents_data.entries
                    if len(tabs) < 1: continue

                    tab = Tab(mdmp, int.from_bytes(tabs[0], 'little'))
                    if not tab.validate(): continue

                    entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                    if len(entries) < 1: continue
                    
                    entry = NavigationEntry(mdmp, int.from_bytes(entries[0], 'little'))
                    if not entry.validate(): continue
                    
                    browser_bases.append(addr)
                except Exception:
                    pass
        
        # Dọn rác bộ nhớ định kỳ
        gc.collect()

    print('### end to find Browser objects at', datetime.datetime.now())
    print(f'### Found {len(browser_bases)} Browser object(s) in memory.')

    print('### start to extract information at', datetime.datetime.now())

    rows = []
    for base in browser_bases:
        try:
            b = Browser(mdmp, base)
            session_id = b.session_id
            
            for ti, tp in enumerate(b.tab_strip_model.contents_data.entries):
                t = Tab(mdmp, int.from_bytes(tp, 'little'))
                w = t.contents
                f = w.primary_frame_tree
                n = f.navigator
                nc = n.controller

                for ei, ep in enumerate(nc.entries.entries):
                    e = NavigationEntry(mdmp, int.from_bytes(ep, 'little'))
                    fe = e.frame_tree.frame_entry
                    rows.append((session_id, ti, e.timestamp.to_datetime(), e.title.string, fe.url.spec.string))
        except Exception:
            pass
        
        gc.collect()

    print('### end to extract information at', datetime.datetime.now())

    headers = ['SessionID', 'Tab', 'Time', 'Title', 'URL']
    dump_name = Path(dump_file).stem
    
    table_output, txt_path, csv_path = save_results(ROOT, f'finder_lowmem_{dump_name}', headers, rows)
    
    print('\n' + table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()