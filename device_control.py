#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
from tabulate import tabulate
import argparse
from tc import TelnetConnect

root_dir = sys.path[0]


def show_info(dev: str, ip: str, mode: str = '', interface_filter: str = 'NOMON',
              auth_file: str = f'{root_dir}/auth.yaml', auth_mode: str = 'mixed',
              login: str = None, password: str = None):

    session = TelnetConnect(ip, device_name=dev)                            # Создаем экземпляр класса

    if login and password:
        session.set_authentication(login=login, password=password)
    else:
        session.set_authentication(mode=auth_mode, auth_file=auth_file)     # Устанавливаем тип аутентификации

    if not session.connect():                                                       # Подключаемся
        sys.exit()

    print(f"\n    Подключаемся к {dev} ({ip})\n"
          f"\n    Тип оборудования: {session.vendor}\n")

    if 'показать_интерфейсы' in mode:
        print(tabulate(session.get_interfaces(), headers='keys', tablefmt="fancy_grid"))

    if 'vlan' in mode:
        print(tabulate(session.get_vlans(), headers='keys', tablefmt="fancy_grid"))
        print(tabulate(session.vlan_info, headers=['VLAN', 'Name', 'Status']))

    if 'mac' in mode:
        print(session.get_mac(description_filter=interface_filter))

    if 'cable-diagnostic' in mode:
        print(session.cable_diagnostic())

    if 'sys-info' in mode:
        print(session.get_device_info())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="telnet control")

    parser.add_argument("-N", dest="device_name", help="device name")
    parser.add_argument("ip", help="device IP")
    parser.add_argument("-m", dest="mode")
    parser.add_argument("--desc-filter", dest="description_filter")
    parser.add_argument("--auth-file", dest="auth_file")
    parser.add_argument("--auth-mode", dest="auth_mode", help="default, group, auto, mixed")
    parser.add_argument("-l", dest="login")
    parser.add_argument("-p", dest="password")

    args = parser.parse_args()
    device_name = args.device_name if args.device_name else ''
    auth_file = args.auth_file if args.auth_file else f'{root_dir}/auth.yaml'
    auth_mode = args.auth_mode if args.auth_mode else 'mixed'
    mode = args.mode if args.mode else ''
    description_filter = args.description_filter if args.description_filter else '\S+'

    show_info(
        dev=device_name,
        ip=args.ip,
        mode=mode,
        interface_filter=description_filter,
        auth_file=auth_file,
        auth_mode=auth_mode,
        login=args.login,
        password=args.password
    )
