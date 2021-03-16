import sys
from core.database import DataBase
from core.tc import TelnetConnect


class DataGather:
    def __init__(self, ip, name):
        self.db = DataBase()
        self.session = TelnetConnect(ip, name)
        self.session.auth_group = self.db.get_item(ip=ip)[0][3] if self.db.get_item(ip=ip) else ''
        self.session.vendor = self.db.get_item(ip=ip)[0][2] if self.db.get_item(ip=ip) else ''

    def collect(self, mode: str = ''):
        if mode not in ['interfaces', 'sys-info']:
            raise Exception(f'Invalid mode for DataGather.collect "{mode}"\nOnly interfaces, sys-info avaliable!')

        if self.session.auth_group:
            self.session.set_authentication(mode='group', auth_group=self.session.auth_group)
        else:
            self.session.set_authentication(mode='mixed')

        if not self.session.connect():
            return 0

        if mode == 'interfaces':
            if self.session.get_interfaces():
                print(f'Interfaces collected! {self.session.device_name} ({self.session.ip})')
        elif mode == 'sys-info':
            if self.session.get_device_info():
                print(f'System information collected! {self.session.device_name} ({self.session.ip})')
        else:
            return 0
