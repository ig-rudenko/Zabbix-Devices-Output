from core.dc import DeviceConnect


class DataGather:
    """
    Реализует процесс сбора состояния портов и системной информации
    """
    def __init__(self, ip, name, auth_group, protocol):
        self.protocol = protocol if protocol and protocol != 'None' else 'telnet'
        self.session = DeviceConnect(ip, name)
        self.session.auth_group = auth_group if auth_group and auth_group != 'None' else ''

    def collect(self, mode: str = ''):
        if mode not in ['interfaces', 'sys-info', 'vlan']:
            raise Exception(f'Invalid mode for DataGather.collect "{mode}"\nOnly (interfaces, sys-info, vlan) avaliable!')

        if self.session.auth_group:
            # Если указана группа авторизации
            self.session.set_authentication(mode='group', auth_group=self.session.auth_group)
        elif self.protocol == 'snmp':
            self.session.set_authentication(mode='snmp')
        else:
            self.session.set_authentication(mode='mixed')

        # Подключаемся с указанным протоколом
        if not self.session.connect(protocol=self.protocol):
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
