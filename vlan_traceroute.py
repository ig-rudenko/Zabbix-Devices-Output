#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import yaml
import argparse
from re import findall, sub
import configparser

clear = '\x1b[0m'
blue = '\x1b[1;34m'
bluefon = '\x1b[1;44m'
yellow = '\x1b[33m'
yellowfon = '\x1b[43m'
green = '\x1b[32m'


def reformatting(name: str):
    with open(f'/{sys.path[0]}/vlan_traceroute/name_format.yaml', 'r') as file:
        name_format = yaml.safe_load(file)
    for n in name_format:
        if n in name:
            return sub(n, name_format[n], name)
    return name


def vlan_range(vlans_ranges: list) -> set:
    """
    Преобразовывает сокращенные диапазоны VLAN'ов в развернутый список

    14, 100-103, 142 -> 14, 100, 101, 102, 103, 142

    :param vlans_ranges: Список диапазонов
    :return: развернутое множество VLAN'ов
    """
    vlans = []
    for v_range in vlans_ranges:
        if len(v_range.split()) > 1:
            vlans += list(vlan_range(v_range.split()))
        try:
            if '-' in v_range:
                parts = v_range.split('-')
                vlans += range(int(parts[0]), int(parts[1])+1)
            else:
                vlans.append(int(v_range))
        except ValueError:
            pass

    return set(vlans)


def find_vlan(device: str, vlan_to_find: int, passed_devices: set, mode: str, desc_re: str, separate: str = '    '):
    """
    Осуществляет поиск VLAN'ов по портам оборудования, которое расположено в папке /root_dir/data/device/
    И имеет файл vlans.yaml

    :param device: Имя устройства, на котором осуществляется поиск
    :param vlan_to_find: VLAN, который ищем
    :param passed_devices:  Уже пройденные устройства
    :param mode: full - отображает имена оборудования и его порты, short - отображает только имена оборудования
    :param separate: Отступ данного устройства относительно его положения в древе
    :return: кол-во устройств ниже по древу, площадь глубины древа ниже
    """
    mode = 'short' if not mode else mode

    passed_devices.add(device)  # Добавляем узел в список уже пройденных устройств
    if not os.path.exists(f'{sys.path[0]}/data/{device}/vlans.yaml'):
        return 0, 0
    with open(f'{sys.path[0]}/data/{device}/vlans.yaml') as file_yaml:
        vlans_yaml = yaml.safe_load(file_yaml)

    interfaces = vlans_yaml['data']
    if not interfaces:
        return 0, 0

    if desc_re and findall(desc_re, device):
        print(separate, f"└ {bluefon}{device}{clear}")  # Выводим отступ и название узла сети
    else:
        print(separate, f"└ {blue}{device}{clear}")  # Выводим отступ и название узла сети
    intf_found_count = 0  # Кол-во найденных интерфейсов на этом устройстве
    devices_down = 0
    tree_mass = 0
    for line in interfaces:
        vlans_list = []  # Список VLAN'ов на порту
        if 'all' in line["VLAN's"]:
            # Если разрешено пропускать все вланы
            vlans_list = list(range(1, 4097))
        else:
            if 'to' in line["VLAN's"]:
                # Если имеется формат "trunk,1 to 7 12 to 44"
                vv = [list(range(int(v[0]), int(v[1]) + 1)) for v in
                      [range_ for range_ in findall(r'(\d+)\s*to\s*(\d+)', line["VLAN's"])]]
                for v in vv:
                    vlans_list += v
            else:
                # Формат представления стандартный "trunk,123,33,10-100"
                vlans_list = vlan_range([v for v in line["VLAN's"].split(',') if
                                         v != 'trunk' and v != 'access' and v != 'hybrid' and v != 'dot1q-tunnel'])
                # Если искомый vlan находится в списке vlan'ов на данном интерфейсе
        if vlan_to_find in vlans_list:
            intf_found_count += 1

            if mode == 'full':
                if desc_re and findall(desc_re, line["Description"]):
                    print(separate, f'└ ({green}{line["Interface"]}{clear}) {yellowfon}{line["Description"]}{clear}')
                else:
                    print(separate, f'└ ({green}{line["Interface"]}{clear}) {yellow}{line["Description"]}{clear}')

            next_device = findall(r'SVSL\S+SW\d+', line["Description"])  # Ищем в описании порта следующий узел сети
            # Приводим к единому формату имя узла сети
            next_device = reformatting(next_device[0]) if next_device else ''
            if next_device and next_device not in list(passed_devices):
                if mode == 'short' and tree_mass > 50 and devices_down > 7:
                    print(f'\n{separate}', f"\x1b[5m┗{clear} {device}  ")  # (устройств выше {devices_down}) масса: {tree_mass}")
                    devices_down = 0
                if mode == 'full' and tree_mass > 5 and devices_down > 2:
                    print(f'\n{separate}', f"\x1b[5m┗{clear} {device}  ")  # (устройств выше {devices_down}) масса: {tree_mass}")
                    devices_down = 0
                dev_down, mass = find_vlan(
                    next_device,
                    vlan_to_find,
                    passed_devices,
                    separate=f'    {separate}',
                    mode=mode,
                    desc_re=desc_re
                )
                if not dev_down:
                    continue
                devices_down += dev_down
                tree_mass += mass

    return devices_down+1, 4*devices_down+tree_mass


if __name__ == '__main__':
    config = configparser.ConfigParser()
    config.read(f'{sys.path[0]}/config')
    try:
        default_device = config.get("VlanTraceroute", "DefaultDeviceName")  # Старт трассировки vlan'ов
    except configparser.NoSectionError:
        default_device = None
    parser = argparse.ArgumentParser(description='VLAN traceroute')
    parser.add_argument('-v', dest='vlan', help='Number of VLAN', type=int, required=True)
    parser.add_argument('-s', dest='start_device', help='First device name', default=default_device)
    parser.add_argument('-m', dest='mode', help='Mode: full (devices and ports), brief (only devices)',
                        choices=['full', 'brief'])
    parser.add_argument('-F', '--find', dest='find', help='regular exception for port description find', metavar='')
    args = parser.parse_args()

    start_device = args.start_device
    if args.vlan and start_device:
        try:
            passed = set()
            print(f'🔎  Начинаем трассировку VLAN > {args.vlan} <\n\n'
                  f'     ┌─ Начальное оборудование')
            status, _ = find_vlan(start_device, args.vlan, passed_devices=passed, mode=args.mode, desc_re=args.find)
            if not status:
                print(f'     └ {start_device} Не найдено!')
            else:
                print(f'\nТрассировка завершена!')
        except KeyboardInterrupt:
            print('\nТрассировка прервана!')
