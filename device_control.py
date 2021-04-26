#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from typing import Union
import argparse
import subprocess
import yaml
import sys
import os

from core.tc import TelnetConnect
from core.tabulate import tabulate
from core.datagather import DataGather
from core.database import DataBase

root_dir = sys.path[0]  # Полный путь к корневой папки


def show_last_saved_data(command: str, device_ip: str, device_name: str) -> None:
    """
    Возвращает последние сохраненные данные (если имеются) из директории <root_dir>/data/<device_name>/

    :param command: Строка команд, какие данные необходимо показать (interfaces, vlan, mac, cable-diagnostic, sys-info)
    :param device_ip:   IP адрес устройства
    :param device_name: Уникальное имя устройства
    :return:            None
    """
    print(f'Оборудование недоступно! ({device_ip})\n')
    if 'show-interfaces' in command and os.path.exists(f'{root_dir}/data/{device_name}/interfaces.yaml'):
        with open(f'{root_dir}/data/{device_name}/interfaces.yaml', 'r') as file:
            interfaces_last_data = yaml.safe_load(file)
            print(f'Последние сохраненные данные: ({interfaces_last_data["saved time"]})\n')
            print(tabulate(interfaces_last_data['data'], headers='keys', tablefmt="fancy_grid"))

    if 'vlan' in command and os.path.exists(f'{root_dir}/data/{device_name}/vlans.yaml') and \
            os.path.exists(f'{root_dir}/data/{device_name}/vlans_info.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{root_dir}/data/{device_name}/vlans.yaml', 'r') as file:
            print(tabulate(yaml.safe_load(file)['data'], headers='keys', tablefmt="fancy_grid"))
        with open(f'{root_dir}/data/{device_name}/vlans_info.yaml', 'r') as file:
            vlans_info = yaml.safe_load(file)['data']
        if isinstance(vlans_info, list):
            if len(vlans_info[0]) == 3:
                print(tabulate(vlans_info, headers=['VLAN', 'Name', 'Status']))
            elif len(vlans_info[0]) == 2:
                print(tabulate(vlans_info, headers=['VLAN', 'Name']))
        else:
            print(yaml.safe_load(file)['data'])

    if 'mac' in command and os.path.exists(f'{root_dir}/data/{device_name}/mac_result.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{root_dir}/data/{device_name}/mac_result.yaml', 'r') as file:
            print(yaml.safe_load(file)['data'])

    if 'cable-diagnostic' in command and os.path.exists(f'{root_dir}/data/{device_name}/cable-diag.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{root_dir}/data/{device_name}/cable-diag.yaml', 'r') as file:
            print(yaml.safe_load(file)['data'])

    if 'sys-info' in command and os.path.exists(f'{root_dir}/data/{device_name}/sys-info.yaml'):
        print('Последние сохраненные данные:\n')
        with open(f'{root_dir}/data/{device_name}/sys-info.yaml', 'r') as file:
            print(yaml.safe_load(file)['data'])


def show_info(device_name: str,
              device_ip: str,
              command: str = '',
              interface_filter: str = r'NOMON',
              authentication_file_path: str = f'{root_dir}/auth.yaml',
              authentication_mode: str = 'mixed',
              authentication_group: str = None,
              login: Union[str, list, None] = None,
              password: Union[str, list, None] = None,
              privilege_mode_password: str = None):
    """
    Осуществляет взаимодействие с оборудованием (указание типа авторизации, подключение, сбор данных, вывод)

    Если оборудование недоступно в данный момент, то будет выведена последняя сохраненная информация.

    :param device_name: Уникальное имя устройства
    :param device_ip:   IP адрес
    :param command: Строка команд, какие данные необходимо собрать (interfaces, vlan, mac, cable-diagnostic, sys-info)
    :param interface_filter: Регулярное выражение. Порты, чье описание совпадает с данным регулярным выражением,
            необходимо добавить в процесс вывода MAC адресов
    :param authentication_file_path: Полный путь к файлу аутентификации
    :param authentication_mode: Тип аутентификации (group, mixed, auto). По умолчанию - mixed
    :param authentication_group: Название группы, которая должна находиться в файле, указанном в переменной
            authentication_file_path. По умолчанию root_dir/auth.yaml
    :param login:
    :param password:
    :param privilege_mode_password:
    :return:
    """

    ip_check = subprocess.run(['ping', '-c', '3', '-n', device_ip], stdout=subprocess.DEVNULL)
    # Проверка на доступность: 0 - доступен, 1 и 2 - недоступен
    if ip_check.returncode == 2:
        print(f'Неправильный ip адрес: {device_ip}')
        return 0

    # Если оборудование недоступно
    elif ip_check.returncode == 1:
        show_last_saved_data(command, device_ip, device_name)

    # Если оборудование доступно
    elif ip_check.returncode == 0:
        session = TelnetConnect(device_ip, device_name=device_name)                       # Создаем экземпляр класса
        if login and password:
            session.set_authentication(login=login, password=password, privilege_mode_password=privilege_mode_password)
        if authentication_group:
            session.set_authentication(mode='group', auth_group=authentication_group, auth_file=authentication_file_path)
        if not authentication_mode or authentication_mode == 'auto':
            session.set_authentication(mode='auto', auth_file=authentication_file_path)
        if authentication_mode == 'mixed':
            session.set_authentication(mode='mixed', auth_file=authentication_file_path)

        if not session.connect():  # Не удалось подключиться
            show_last_saved_data(command, device_ip, device_name)
            return 0

        print(f"\n    Подключаемся к {device_name} ({device_ip})\n"
              f"\n    Тип оборудования: {session.device['vendor']} {session.device['model']}\n")

        if 'show-interfaces' in command:
            print(tabulate(session.get_interfaces(), headers='keys', tablefmt="fancy_grid"))

        if 'vlan' in command:
            print(tabulate(session.get_vlans(), headers='keys', tablefmt="fancy_grid"))
            if isinstance(session.vlan_info, list):
                print(tabulate(session.vlan_info, headers=['VLAN', 'Name', 'Status']))
            else:
                print(session.vlan_info)

        if 'mac' in command:
            print(session.get_mac(description_filter=interface_filter))

        if 'cable-diagnostic' in command:
            print(session.cable_diagnostic())

        if 'sys-info' in command:
            print(session.get_device_info())


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="telnet control")

    parser.add_argument("-N", dest="device_name", help="device name", default='')
    parser.add_argument("-i", dest='ip', help="device IP")
    parser.add_argument("-m", dest="mode", help="show-interfaces, vlan, mac, sys-info, cable-diagnostic", default='')
    parser.add_argument("--desc-filter", dest="description_filter", default=r'\S+')
    parser.add_argument("--auth-file", dest="auth_file", default=f'{root_dir}/auth.yaml')
    parser.add_argument("--auth-mode", dest="auth_mode", help="default, group, auto, mixed", default='mixed')
    parser.add_argument("--auth-group", dest="auth_group", help="groups from auth file", default=None)
    parser.add_argument("--data-gather", dest="data_gather", help="Collect data from devices in database "
                                                                  "(interfaces, sys-info)")
    parser.add_argument("-l", dest="login")
    parser.add_argument("-p", dest="password")
    parser.add_argument("--zabbix-rebase-from-groups", dest="zabbix_rebase_groups", type=str,
                        help="List zabbix group names separated by commas, no spaces 'group1,group2,group3'")
    args = parser.parse_args()

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
        groups_ids = zabbix.hostgroup.get(filter={"name": args.zabbix_rebase_groups.split(',')})
        for group in groups_ids:
            hosts = zabbix.host.get(groupids=group['groupid'], selectInterfaces=['ip'])  # Список узлов сети в группе
            for host in hosts:  # Для каждого найденного узла сети
                if host["status"] == '1':
                    continue  # Пропускаем деактивированный узел сети
                item = db.get_item(ip=host['interfaces'][0]['ip'])
                if item and item[0][1] != host["host"]:
                    # Обновляем имя узла сети, если он уже имеется в базе и имена отличаются
                    print('Обновляем', host["host"], host['interfaces'][0]['ip'])
                    db.update(
                        ip=host['interfaces'][0]['ip'],
                        update_data=[
                            (host['interfaces'][0]['ip'], host['host'], item[0][2], item[0][3])
                        ]
                    )
                elif not item:
                    # Создаем новую запись в таблицу
                    print('Добавляем', host["host"], host['interfaces'][0]['ip'])
                    db.add_data(
                        data=[
                            (host['interfaces'][0]['ip'], host['host'], '', '')
                        ]
                    )
        sys.exit()

    if args.data_gather:
        # Автоматический сбор информации
        db = DataBase()
        table = db.get_table()
        with ThreadPoolExecutor() as executor:
            for line in table:
                data_gather = DataGather(ip=line[0], name=line[1], auth_group=line[3])
                executor.submit(data_gather.collect, args.data_gather)
        sys.exit()

    show_info(
        device_name=args.device_name,
        device_ip=args.ip,
        command=args.mode,
        interface_filter=args.description_filter,
        authentication_file_path=args.auth_file,
        authentication_mode=args.auth_mode,
        authentication_group=args.auth_group,
        login=args.login,
        password=args.password
    )
