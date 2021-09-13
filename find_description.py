#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import yaml
import argparse
from re import findall


def admin_status_color(admin_status: str) -> str:
    if findall(r'down|DOWN|\*|Dis', admin_status):
        return f'\x1b[5;41m{admin_status}\x1b[0m'
    else:
        return f'\x1b[1;32m{admin_status}\x1b[0m'


def find_description(find_str: list, find_re: list, mode: str, enable_print: bool = True, color: bool = True):
    result = []
    finding_string = '|'.join(find_str).lower()

    re_string = '|'.join(find_re)
    if enable_print:
        print(f'Начинаем поиск')
        if color:
            print(f'Описание > \x1b[1;32m{", ".join(find_str)}\x1b[0m <\n' if finding_string else '', end='')
            print(f"Regular exception > \x1b[1;32m{re_string}\x1b[0m <\n" if re_string else "")
        else:
            print(f'Описание > {", ".join(find_str)} <\n' if finding_string else '', end='')
            print(f"Regular exception > {re_string}\n" if re_string else "")

    try:
        for device in os.listdir(f'{sys.path[0]}/data'):
            if os.path.exists(f'{sys.path[0]}/data/{device}/interfaces.yaml'):
                with open(f'{sys.path[0]}/data/{device}/interfaces.yaml', 'r') as intf_yaml:
                    interfaces = yaml.safe_load(intf_yaml)
                for line in interfaces['data']:
                    if (findall(finding_string, line['Description'].lower()) and find_str) or \
                            (findall(re_string, line['Description']) and find_re):
                        # Если нашли совпадение в строке
                        status = line.get('Admin Status') or line.get('Link Status') or line.get('Port Status') \
                                 or line.get('Status')
                        result.append(
                            {
                                'Device': device,
                                'Interface': line['Interface'],
                                'Description': line['Description'],
                                'Status': status
                            }
                        )
                        if enable_print:
                            if color:
                                print(f'Оборудование: \x1b[1;34m{device}\x1b[0m')
                                print(f'    Порт: \x1b[32m{line["Interface"]}\x1b[0m ', end='')
                                print(f'Status: {admin_status_color(status)} ' if mode == 'full' else '', end='')
                                print(f'Descr: \x1b[33m{line["Description"].strip()}\x1b[0m\n'
                                      if mode == 'full' or mode == 'brief' else '')
                            else:
                                print(f'Оборудование: {device}')
                                print(f'    Порт: {line["Interface"]}, ', end='')
                                print(f'Status: {admin_status_color(status)}, ' if mode == 'full' else '', end='')
                                print(f'Descr: {line["Description"].strip()}\n'
                                      if mode == 'full' or mode == 'brief' else '')
    except KeyboardInterrupt:
        print('\nПоиск прерван')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Find Description")

    parser.add_argument('-d', dest="description", nargs='+', help="Description", metavar='')
    parser.add_argument("-re", dest='re', help='regular exception', nargs='+', metavar='')
    parser.add_argument("-m", dest='mode', help='', default='brief', choices=['device', 'brief', 'full'])
    parser.add_argument('--color', dest='color', help='color output (yes/no)', default='yes', metavar='')
    args = parser.parse_args()

    if not args.description and not args.re:
        sys.exit('Не указаны параметры поиска\nСмотрите: find-description [-h, --help]')

    desc_res = find_description(
        find_str=args.description or [],
        find_re=args.re or [],
        mode=args.mode,
        color=False if args.color == 'no' else True
    )
    print(f'Всего найдено: {len(desc_res)}')
