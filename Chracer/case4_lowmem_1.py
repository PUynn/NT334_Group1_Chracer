#!/usr/bin/env python3
import argparse
import datetime
import gc
import sys
from pathlib import Path

from minidump.minidumpfile import MinidumpFile

from lowmem_runtime import configure_lowmem_symbols, save_results
# IMPORT MODULE BẢO TOÀN CHỨNG CỨ
from acquisition.hash_dump import preserve_evidence
ROOT = Path(__file__).resolve().parent
DEFAULT_DUMP = ROOT / 'dumps' / 'case4.dmp'
DEFAULT_BASES = [1885639781552]


def parse_args():
    p = argparse.ArgumentParser(description='Low-memory extractor for case4.')
    p.add_argument('--dump', default=str(DEFAULT_DUMP), help='Path to dump file')
    p.add_argument('--bases', nargs='*', type=lambda x: int(x, 0), default=DEFAULT_BASES)
    return p.parse_args()


def main():
    args = parse_args()
    preserve_evidence(args.dump)
    
    print('### start to load symbols at', datetime.datetime.now())
    sys.stdout.flush()
    configure_lowmem_symbols(ROOT)
    from chracer.chromium import Browser, Tab, NavigationEntry
    print('### end to load symbols at', datetime.datetime.now())

    print('### start to extract information at', datetime.datetime.now())
    mdmp = MinidumpFile.parse(args.dump)
    rows = []

    def safe(getter, default=''):
        try:
            return getter()
        except Exception:
            return default

    for base in args.bases:
        print('### processing Browser base 0x{:X}'.format(base))
        try:
            browser = Browser(mdmp, base)

            tabs = browser.tab_strip_model.contents_data.entries
            for tab_base in tabs:
                tab_base = int.from_bytes(tab_base, 'little')
                tab = Tab(mdmp, tab_base)

                nav_entries = tab.contents.primary_frame_tree.navigator.controller.entries.entries
                for nav_entry_base_raw in nav_entries:
                    try:
                        nav_entry_base = int.from_bytes(nav_entry_base_raw, 'little')
                        nav_entry = NavigationEntry(mdmp, nav_entry_base)
                        if not nav_entry.validate():
                            continue
                        if not nav_entry.ssl or not nav_entry.ssl.certificate:
                            continue

                        crt = nav_entry.ssl.certificate
                        serial = safe(lambda: crt.serial_number, '')
                        common_name = safe(lambda: crt.subject.common_name.string, '')
                        issuer = safe(lambda: crt.issuer.common_name.string, '')
                        valid_start = safe(lambda: crt.valid_start.to_datetime(), '')
                        valid_expiry = safe(lambda: crt.valid_expiry.to_datetime(), '')
                        if serial or common_name or issuer or valid_start or valid_expiry:
                            rows.append((serial, common_name, issuer, valid_start, valid_expiry))
                    except Exception as e:
                        bad_base = int.from_bytes(nav_entry_base_raw, 'little')
                        print('[WARN] 0x{:X} cert parse error ({})'.format(bad_base, e))
                        continue
                gc.collect()
        except Exception as e:
            print('[WARN] 0x{:X} processing error ({})'.format(base, e))

    print('### end to extract information at', datetime.datetime.now())
    headers = ['SerialNumber', 'CommonName', 'Issuer', 'ValidStart', 'ValidExpiry']
    table_output, txt_path, csv_path = save_results(ROOT, 'case4_lowmem', headers, rows)
    print(table_output)
    print(f'### saved text result to {txt_path}')
    print(f'### saved csv result to {csv_path}')


if __name__ == '__main__':
    main()
