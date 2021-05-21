#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from concurrent.futures import ThreadPoolExecutor
import argparse
import subprocess
import yaml
import sys
import os

from core.dc import DeviceConnect
from core.tabulate import tabulate
from core.datagather import DataGather
from core.database import DataBase


def parse_argument():
    parser = argparse.ArgumentParser(description="Device control script")

    parser.add_argument("-N", "--name", dest="device_name", help="Device name", default='', metavar='')
    parser.add_argument("-i", "--ip", dest='ip', help="Device IP", default='', metavar='')
    parser.add_argument("-P", dest='protocol', help="Protocol type (default telnet)", default='telnet',
                        choices=['ssh', 'telnet', 'snmp'])
    parser.add_argument("-c", dest='snmp_community', help="SNMP v2c community", default='public')
    parser.add_argument("--snmp-port", dest='snmp_port', help='SNMP v2c port (default 161)', default='161', metavar='')
    parser.add_argument("-m", "--mode", dest="mode", nargs='*',
                        help="Output (show-interfaces, vlan, mac, sys-info, cable-diagnostic)", default='',
                        choices=['show-interfaces', 'vlan', 'mac', 'sys-info', 'cable-diagnostic'], metavar='')
    parser.add_argument("--desc-filter", dest="description_filter", default=r'\S+',
                        help='Regular exception (default \'\\S+)\'')
    parser.add_argument("--auth-file", dest="auth_file", default=f'{sys.path[0]}/auth.yaml')
    parser.add_argument("--auth-mode", dest="auth_mode", help="Authorization type (default mixed)", default='mixed',
                        choices=['default', 'group', 'auto', 'mixed'])
    parser.add_argument("--auth-group", dest="auth_group", help="Groups from auth file", default=None)
    parser.add_argument("--data-gather", dest="data_gather", help="Collect data from devices in database \n"
                                                                  "(interfaces, sys-info, vlan)",
                        choices=['interfaces', 'sys-info', 'vlan'])
    parser.add_argument("-l", "--login", dest="login", help='For telnet/ssh', metavar='')
    parser.add_argument("-p", "--passwd", dest="password", help='For telnet/ssh', metavar='')
    parser.add_argument("--secret-pass", dest="privilege_mode_password", help='For telnet/ssh')
    parser.add_argument("--zabbix-rebase", dest="zabbix_rebase_groups", nargs='+',
                        help="Zabbix groups names", metavar='GROUPS')
    return parser.parse_args()


def show_last_saved_data(command, device_ip: str, device_name: str) -> None:
    """
    Возвращает последние сохраненные данные (если имеются) из директории <root_dir>/data/<device_name>/

    :param command: Строка команд, какие данные необходимо показать (interfaces, vlan, mac, cable-diagnostic, sys-info)
    :param device_ip:   IP адрес устройства
    :param device_name: Уникальное имя устройства
    :return:            None
    """
    print(f'Оборудование недоступно! ({device_ip})\n')
    if 'show-interfaces' in command and os.path.exists(f'{sys.path[0]}/data/{device_name}/interfaces.yaml'):
        with open(f'{sys.path[0]}/data/{device_name}/interfaces.yaml', 'r') as file:
            interfaces_last_data = yaml.safe_load(file)
            print(f'Последние сохраненные данные: ({interfaces_last_data["saved time"]})\n')
            print(tabulate(interfaces_last_data['data'], headers='keys', tablefmt="fancy_grid"))

    if 'vlan' in command and os.path.exists(f'{sys.path[0]}/data/{device_name}/vlans.yaml') and \
            os.path.exists(f'{sys.path[0]}/data/{device_name}/vlans_info.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{sys.path[0]}/data/{device_name}/vlans.yaml', 'r') as file:
            print(tabulate(yaml.safe_load(file)['data'], headers='keys', tablefmt="fancy_grid"))
        with open(f'{sys.path[0]}/data/{device_name}/vlans_info.yaml', 'r') as file:
            vlans_info = yaml.safe_load(file)['data']
        if isinstance(vlans_info, list):
            if len(vlans_info[0]) == 3:
                print(tabulate(vlans_info, headers=['VLAN', 'Name', 'Status']))
            elif len(vlans_info[0]) == 2:
                print(tabulate(vlans_info, headers=['VLAN', 'Name']))
        else:
            print(yaml.safe_load(file)['data'])

    if 'mac' in command and os.path.exists(f'{sys.path[0]}/data/{device_name}/mac_result.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{sys.path[0]}/data/{device_name}/mac_result.yaml', 'r') as file:
            print(yaml.safe_load(file)['data'])

    if 'cable-diagnostic' in command and os.path.exists(f'{sys.path[0]}/data/{device_name}/cable-diag.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{sys.path[0]}/data/{device_name}/cable-diag.yaml', 'r') as file:
            print(yaml.safe_load(file)['data'])

    if 'sys-info' in command and os.path.exists(f'{sys.path[0]}/data/{device_name}/sys-info.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{sys.path[0]}/data/{device_name}/sys-info.yaml', 'r') as file:
            print(yaml.safe_load(file)['data'])


if __name__ == '__main__':
    args = parse_argument()
    if args.zabbix_rebase_groups:
        # Обновляем базу из Zabbix
        from core.pyzabbix.api import ZabbixAPI
        from configparser import ConfigParser
        config = ConfigParser()
        config.read(f'{sys.path[0]}/config')
        zabbix_url = config.get("Zabbix", "ZabbixURL")
        zabbix_login = config.get("Zabbix", "ZabbixAPILogin")
        zabbix_pass = config.get("Zabbix", "ZabbixAPIPassword")

        db = DataBase()
        zabbix = ZabbixAPI(url=zabbix_url, user=zabbix_login, password=zabbix_pass)
        groups_ids = zabbix.hostgroup.get(filter={"name": args.zabbix_rebase_groups})
        for group in groups_ids:
            hosts = zabbix.host.get(groupids=group['groupid'], selectInterfaces=['ip'])  # Список узлов сети в группе
            for host in hosts:  # Для каждого найденного узла сети
                if host["status"] == '1':
                    continue  # Пропускаем деактивированный узел сети
                item = db.get_item(ip=host['interfaces'][0]['ip'])
                if item and item[0][1] != host["host"]:
                    # Обновляем имя узла сети, если он уже имеется в базе и имена отличаются
                    print('Обновляем', host["host"], host['interfaces'][0]['ip'])
                    db.update(ip=host['interfaces'][0]['ip'], device_name=host['host'])
                elif not item:
                    # Создаем новую запись в таблицу
                    print('Добавляем', host["host"], host['interfaces'][0]['ip'])
                    db.add_data(
                        data=[
                            (host['interfaces'][0]['ip'], host['host'], '', '', 'snmp', '')
                        ]
                    )
        sys.exit()

    if args.data_gather:
        # Автоматический сбор информации
        db = DataBase()
        table = db.get_table()
        with ThreadPoolExecutor() as executor:
            for line in table:
                if 'DSL' in line[1]:
                    data_gather = DataGather(ip=line[0], name=line[1], auth_group=line[3], protocol=line[4])
                    executor.submit(data_gather.collect, args.data_gather)
        sys.exit()

    ip_check = subprocess.run(['ping', '-c', '3', '-n', args.ip], stdout=subprocess.DEVNULL)
    # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен
    if ip_check.returncode == 2:
        print(f'Неправильный ip адрес: {args.ip}')
        sys.exit(1)

    # Если оборудование недоступно
    elif ip_check.returncode == 1:
        show_last_saved_data(args.mode, args.ip, args.device_name)

    # Если оборудование доступно
    elif ip_check.returncode == 0:
        session = DeviceConnect(args.ip, device_name=args.device_name)  # Создаем экземпляр класса

        if args.protocol == 'snmp':
            args.auth_mode = 'snmp'
            session.set_authentication(mode='snmp', snmp_community=args.snmp_community, snmp_port=args.snmp_port)

        if args.login and args.password:
            session.set_authentication(
                login=args.login,
                password=args.password,
                privilege_mode_password=args.privilege_mode_password
            )
        if args.auth_group:
            session.set_authentication(mode='group', auth_group=args.auth_group,
                                       auth_file=args.auth_file)
        if not args.auth_mode or args.auth_mode == 'auto':
            session.set_authentication(mode='auto', auth_file=args.auth_file)
        if args.auth_mode == 'mixed':
            session.set_authentication(mode='mixed', auth_file=args.auth_file)

        if not session.connect(protocol=args.protocol):  # Не удалось подключиться
            show_last_saved_data(args.mode, args.ip, args.device_name)
            sys.exit(1)

        print(f"\n    Подключаемся к {args.device_name} ({args.ip})\n")
        print(f"\n    Тип оборудования: {session.device['vendor']} {session.device['model']}\n"
              if session.device['vendor'] and session.device['model'] else '')

        if 'show-interfaces' in args.mode:
            print(tabulate(session.get_interfaces(), headers='keys', tablefmt="fancy_grid"))
            if args.protocol == 'snmp':
                print(session.device['snmp_interfaces_status_help'])

        if 'vlan' in args.mode:
            print(tabulate(session.get_vlans(), headers='keys', tablefmt="fancy_grid"))
            if isinstance(session.vlan_info, list):
                print(tabulate(session.vlan_info, headers=['VLAN', 'Name', 'Status']))
            else:
                print(session.vlan_info)

        if 'mac' in args.mode:
            print(session.get_mac(description_filter=args.description_filter))

        if 'cable-diagnostic' in args.mode:
            print(session.cable_diagnostic())

        if 'sys-info' in args.mode:
            print(session.get_device_info())
