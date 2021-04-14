import sys
from core.database import DataBase
from core.tc import TelnetConnect


class DataGather:
    """
    Реализует процесс сбора состояния портов и системной информации
    """
    def __init__(self, ip, name, auth_group):
        self.session = TelnetConnect(ip, name)
        self.session.auth_group = auth_group if auth_group and auth_group != 'None' else ''

    def collect(self, mode: str = ''):
        if mode not in ['interfaces', 'sys-info', 'vlan']:
            raise Exception(f'Invalid mode for DataGather.collect "{mode}"\nOnly interfaces, sys-info, vlan avaliable!')

        if self.session.auth_group:
            self.session.set_authentication(mode='group', auth_group=self.session.auth_group)
        else:
            self.session.set_authentication(mode='mixed')

        if not self.session.connect():
            return 0

        if mode == 'interfaces':
            if self.session.get_interfaces():
                print(f'Interfaces collected! {self.session.device["name"]} ({self.session.device["ip"]})')
        if mode == 'vlan':
            if self.session.get_vlans():
                print(f'VLAN\'s collected! {self.session.device["name"]} ({self.session.device["ip"]})')
        elif mode == 'sys-info':
            if self.session.get_device_info():
                print(f'System information collected! {self.session.device["name"]} ({self.session.device["ip"]})')
        else:
            return 0
