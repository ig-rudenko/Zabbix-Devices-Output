#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pexpect
from re import findall
import sys
from vendors import *
import yaml
import ipaddress

root_dir = sys.path[0]


def ip_range(ip_input_range_list: list):
    result = []
    for ip_input_range in ip_input_range_list:
        if '/' in ip_input_range:
            try:
                ip = ipaddress.ip_network(ip_input_range)
            except ValueError:
                ip = ipaddress.ip_interface(ip_input_range).network
            return [str(i) for i in list(ip.hosts())]
        range_ = {}
        ip = ip_input_range.split('.')
        for num, oct in enumerate(ip, start=1):
            if '-' in oct:
                ip_range = oct.split('-')
                ip_range[0] = ip_range[0] if 0 <= int(ip_range[0]) < 256 else 0
                ip_range[1] = ip_range[0] if 0 <= int(ip_range[1]) < 256 else 0
                range_[num] = oct.split('-')
            elif 0 <= int(oct) < 256:
                range_[num] = [oct, oct]
            else:
                range_[num] = [0, 0]

        for oct1 in range(int(range_[1][0]), int(range_[1][1])+1):
            for oct2 in range(int(range_[2][0]), int(range_[2][1])+1):
                for oct3 in range(int(range_[3][0]), int(range_[3][1])+1):
                    for oct4 in range(int(range_[4][0]), int(range_[4][1])+1):
                        result.append(f'{oct1}.{oct2}.{oct3}.{oct4}')
    return result


class TelnetConnect:
    def __init__(self, ip: str, device_name: str = ''):
        self.device_name = device_name
        self.ip = ip
        self.auth_mode = 'default'
        self.auth_file = f'{root_dir}/auth.yaml'
        self.auth_group = None
        self.login = []
        self.password = []
        self.telnet_session = None
        self.vendor = None
        self.interfaces = []
        self.raw_interfaces = []
        self.device_info = None
        self.mac_last_result = None
        self.vlans = None
        self.vlan_info = None
        self.cable_diag = None

    def set_authentication(self, mode: str = 'default', auth_file: str = f'{root_dir}/auth.yaml',
                           auth_group: str = None, login=None, password=None):
        self.auth_mode = mode
        self.auth_file = auth_file
        self.auth_group = auth_group

        if self.auth_mode.lower() == 'default' or self.auth_mode.lower() == 'group':
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                self.login = ['admin'] if not self.auth_group else [auth_dict['GROUPS'][self.auth_group]['login']]
                self.password = ['admin'] if not self.auth_group else [auth_dict['GROUPS'][self.auth_group]['password']]

            except Exception:
                self.login = ['admin']
                self.password = ['admin']

        if self.auth_mode.lower() == 'auto':
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                for group in auth_dict["GROUPS"]:
                    iter_dict = auth_dict["GROUPS"][group]  # Записываем группу в отдельзую переменную
                    # Если есть ключ 'devices_by_name' и в нем имеется имя устройства ИЛИ
                    # есть ключ 'devices_by_ip' и в нем имеется IP устройства
                    if (iter_dict.get('devices_by_name') and self.device_name in iter_dict.get('devices_by_name')) \
                            or (iter_dict.get('devices_by_ip') and self.ip in ip_range(iter_dict.get('devices_by_ip'))):
                        # Логин равен списку логинов найденных в элементе 'login' или 'admin'
                        self.login = (iter_dict['login'] if isinstance(iter_dict['login'], list)
                                      else [iter_dict['login']]) if iter_dict.get('login') else ['admin']
                        # Логин равен списку паролей найденных в элементе 'password' или 'admin'
                        self.password = (iter_dict['password'] if isinstance(iter_dict['password'], list)
                                         else [iter_dict['password']]) if iter_dict.get('password') else ['admin']
                        break
                else:
                    self.login = ['admin']
                    self.password = ['admin']

            except Exception:
                self.login = ['admin']
                self.password = ['admin']

        if login and password:
            self.login = login if isinstance(login, list) else [login]
            self.password = password if isinstance(password, list) else [password]

        if self.auth_mode == 'mixed':
            try:
                with open(self.auth_file, 'r') as file:
                    auth_dict = yaml.safe_load(file)
                self.login = auth_dict['MIXED']['login']
                self.password = auth_dict['MIXED']['password']

            except Exception:
                self.login = ['admin']
                self.password = ['admin']

    def connect(self):
        if not self.login or not self.password:
            self.set_authentication()

        self.telnet_session = pexpect.spawn(f"telnet {self.ip}")
        try:
            for login, password in zip(self.login, self.password):
                login_stat = self.telnet_session.expect(
                    ["[Ll]ogin", "[Uu]ser", "[Nn]ame", 'Unable to connect', 'Connection closed'],
                    timeout=20
                )
                if login_stat >= 3:
                    print("    Telnet недоступен!")
                    return False
                self.telnet_session.sendline(login)
                self.telnet_session.expect("[Pp]ass")
                self.telnet_session.sendline(password)
                match = self.telnet_session.expect(
                    [r']$', r'>$', r'#', r'Failed to send authen-req', r"[Ll]ogin(?!-)", r"[Uu]ser\s", r"[Nn]ame",
                     r'Fail!']
                )
                if match < 3:
                    break
            else:  # Если не удалось зайти под логинами и паролями из списка аутентификации
                print('    Неверный логин или пароль!')
                return False
            # print(f"    Подключаемся к {self.device_name} ({self.ip})\n")
            self.telnet_session.sendline('show version')
            version = ''
            while True:
                m = self.telnet_session.expect([r']$', '-More-', r'>$', r'#', pexpect.TIMEOUT])
                version += str(self.telnet_session.before.decode('utf-8'))
                if m == 1:
                    self.telnet_session.sendline(' ')
                if m == 4:
                    self.telnet_session.sendcontrol('C')
                else:
                    break

            if ' ZTE Corporation:' in version:
                self.vendor = 'zte'
            if 'Unrecognized command' in version:
                self.vendor = 'huawei'
            if 'cisco' in version.lower():
                self.vendor = 'cisco'
            if 'Next possible completions:' in version:
                self.vendor = 'd-link'
            if findall(r'SW version\s+', version):
                self.vendor = 'alcatel_or_lynksys'
            if 'Hardware version' in version:
                self.vendor = 'edge-core'
            if 'Active-image:' in version:
                self.vendor = 'eltex-mes'
            if 'Boot version:' in version:
                self.vendor = 'eltex-esr'
            if 'ExtremeXOS' in version:
                self.vendor = 'extreme'
            if 'QTECH' in version:
                self.vendor = 'q-tech'

        except pexpect.exceptions.TIMEOUT:
            print("    Время ожидания превышено! (timeout)")
            return False

    def get_interfaces(self):
        if 'cisco' in self.vendor:
            self.raw_interfaces = cisco.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in self.raw_interfaces
            ]
        if 'd-link' in self.vendor:
            self.raw_interfaces = d_link.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in self.raw_interfaces
            ]
        if 'huawei' in self.vendor:
            self.raw_interfaces, self.vendor = huawei.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Port Status': line[1], 'Description': line[2]}
                for line in self.raw_interfaces
            ]
        if 'zte' in self.vendor:
            self.raw_interfaces = zte.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in self.raw_interfaces
            ]
        if 'alcatel' in self.vendor or 'lynksys' in self.vendor:
            interfaces_list = alcatel_linksys.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in interfaces_list
            ]
        if 'edge-core' in self.vendor:
            self.raw_interfaces = edge_core.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in self.raw_interfaces
            ]
        if 'eltex' in self.vendor:
            self.raw_interfaces = eltex.show_interfaces(telnet_session=self.telnet_session, eltex_type=self.vendor)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in self.raw_interfaces
            ]
        if 'extreme' in self.vendor:
            self.raw_interfaces = extreme.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3]}
                for line in self.raw_interfaces
            ]
        if 'q-tech' in self.vendor:
            self.raw_interfaces, self.vendor = huawei.show_interfaces(telnet_session=self.telnet_session)
            self.interfaces = [
                {'Interface': line[0], 'Link Status': line[1], 'Description': line[2]}
                for line in self.raw_interfaces
            ]
        return self.interfaces

    def get_device_info(self):
        if 'cisco' in self.vendor:
            self.device_info = cisco.show_device_info(telnet_session=self.telnet_session)
        if 'd-link' in self.vendor:
            self.device_info = d_link.show_device_info(telnet_session=self.telnet_session)
        if 'huawei' in self.vendor:
            self.device_info = huawei.show_device_info(telnet_session=self.telnet_session)
        if 'zte' in self.vendor:
            self.device_info = zte.show_device_info(telnet_session=self.telnet_session)
        if 'alcatel' in self.vendor or 'lynksys' in self.vendor:
            self.device_info = alcatel_linksys.show_device_info(telnet_session=self.telnet_session)
        if 'edge-core' in self.vendor:
            self.device_info = edge_core.show_device_info(telnet_session=self.telnet_session)
        if 'eltex' in self.vendor:
            self.device_info = eltex.show_device_info(telnet_session=self.telnet_session)
        if 'extreme' in self.vendor:
            self.device_info = extreme.show_device_info(telnet_session=self.telnet_session)
        if 'q-tech' in self.vendor:
            self.device_info = qtech.show_device_info(telnet_session=self.telnet_session)
        return self.device_info

    def get_mac(self, description_filter: str = '\S+'):
        if not self.raw_interfaces:
            self.get_interfaces()
        if 'cisco' in self.vendor:
            self.mac_last_result = cisco.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        if 'd-link' in self.vendor:
            self.mac_last_result = d_link.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        if 'huawei-1' in self.vendor:
            self.mac_last_result = huawei.show_mac_huawei_1(self.telnet_session, self.raw_interfaces,
                                                            description_filter)
        if 'huawei-2' in self.vendor:
            self.mac_last_result = huawei.show_mac_huawei_2(self.telnet_session, self.raw_interfaces,
                                                            description_filter)
        if 'zte' in self.vendor:
            self.mac_last_result = zte.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        if 'alcatel' in self.vendor or 'lynksys' in self.vendor:
            self.mac_last_result = "Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉"
            # self.mac_last_result = alcatel_linksys.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        if 'edge-core' in self.vendor:
            self.mac_last_result = "Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉"
            # self.mac_last_result = edge_core.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        if 'eltex-mes' in self.vendor:
            self.mac_last_result = eltex.show_mac_mes(self.telnet_session, self.raw_interfaces, description_filter)
        if 'eltex-esr' in self.vendor:
            self.mac_last_result = eltex.show_mac_esr_12vf(self.telnet_session)
        if 'extreme' in self.vendor:
            self.mac_last_result = extreme.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        if 'q-tech' in self.vendor:
            self.mac_last_result = qtech.show_mac(self.telnet_session, self.raw_interfaces, description_filter)
        return self.mac_last_result

    def get_vlans(self):
        if not self.raw_interfaces:
            self.get_interfaces()
        if 'cisco' in self.vendor:
            self.vlan_info, vlans_last_result = cisco.show_vlans(self.telnet_session, self.raw_interfaces)
            self.vlans = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3],
                 "VLAN's": line[4]}
                for line in vlans_last_result
            ]
        if 'd-link' in self.vendor:
            self.vlan_info, vlans_last_result = d_link.show_vlans(self.telnet_session, self.raw_interfaces)
            self.vlans = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3],
                 "VLAN's": line[4]}
                for line in vlans_last_result
            ]
        if 'huawei' in self.vendor:
            self.vlan_info, vlans_last_result = huawei.show_vlans(self.telnet_session, self.raw_interfaces)
            self.vlans = [
                {'Interface': line[0], 'Port Link': line[1], 'Description': line[2], "VLAN's": line[3]}
                for line in vlans_last_result
            ]
        if 'zte' in self.vendor:
            self.vlans_last_result = "Для данного типа оборудования просмотр VLAN'ов в данный момент недоступен 🦉"
            # self.vlans_last_result = zte.show_vlans(self.telnet_session, self.raw_interfaces)
        if 'alcatel' in self.vendor or 'lynksys' in self.vendor:
            self.vlans_last_result = "Для данного типа оборудования просмотр VLAN'ов в данный момент недоступен 🦉"
            # self.vlans_last_result = alcatel_linksys.show_vlans(self.telnet_session, self.raw_interfaces)
        if 'edge-core' in self.vendor:
            self.vlans_last_result = "Для данного типа оборудования просмотр VLAN'ов в данный момент недоступен 🦉"
            # self.vlans_last_result = edge_core.show_vlans(self.telnet_session, self.raw_interfaces)
        if 'eltex' in self.vendor:
            self.vlan_info, vlans_last_result = eltex.show_vlans(self.telnet_session, self.raw_interfaces)
            self.vlans = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3],
                 "VLAN's": line[4]}
                for line in vlans_last_result
            ]
        if 'extreme' in self.vendor:
            self.vlan_info, vlans_last_result = extreme.show_vlans(self.telnet_session, self.raw_interfaces)
            self.vlans = [
                {'Interface': line[0], 'Admin Status': line[1], 'Link': line[2], 'Description': line[3],
                 "VLAN's": line[4]}
                for line in vlans_last_result
            ]
        if 'q-tech' in self.vendor:
            self.vlans_last_result = "Для данного типа оборудования просмотр VLAN'ов в данный момент недоступен 🦉"
            # self.vlans_last_result = qtech.show_vlans(self.telnet_session, self.raw_interfaces)
        return self.vlans

    def cable_diagnostic(self):
        if 'd-link' in self.vendor:
            self.cable_diag = d_link.show_cable_diagnostic(telnet_session=self.telnet_session)
        if 'huawei' in self.vendor:
            self.cable_diag = huawei.show_cable_diagnostic(telnet_session=self.telnet_session)
        return self.cable_diag
