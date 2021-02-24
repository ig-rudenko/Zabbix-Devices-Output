import pexpect
from re import findall, sub
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_mac_huawei_1(telnet_session, interfaces: list, interface_filter: str) -> str:
    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    not_uplinks = True if interface_filter == 'only-abonents' else False

    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[2].upper() and  # - интерфейсов, которые содержат "SVSL"
                    'HUAWEI, QUIDWAY' not in line[2].upper() and  # - "заглушек" типа "HUAWEI, Quidway Series
                    'POWER_MONITORING' not in line[2].upper())  # - POWER_MONITORING
                and 'down' not in line[1].lower()  # И только интерфейсы со статусом admin up
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[2]])

    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

    for intf in intf_to_check:  # для каждого интерфейса
        telnet_session.sendline(f'display mac-address {interface_normal_view(intf[0])}')
        telnet_session.expect(f'{interface_normal_view(intf[0])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n'
        while True:
            match = telnet_session.expect([r'<', "  ---- More ----", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8'))
            mac_output += page.strip()
            if match == 0:
                break
            elif match == 1:
                telnet_session.send(" ")
                mac_output += '\n'
            else:
                print("    Ошибка: timeout")
                break
        mac_output += '\n'
    return mac_output


def show_mac_huawei_2(telnet_session, interfaces: list, interface_filter: str) -> str:
    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    # Все интерфейсы, кроме аплинков
    not_uplinks = True if interface_filter == '--only-abonents' else False

    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[2])))  # интерфейсы по фильтру
                or (not_uplinks and                          # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[2].upper() and             # - интерфейсов, которые содержат "SVSL"
                    'HUAWEI, QUIDWAY' not in line[2].upper() and  # - "заглушек" типа "HUAWEI, Quidway Series
                    'POWER_MONITORING' not in line[2].upper())    # - POWER_MONITORING
                and 'down' not in line[1].lower()            # И только интерфейсы со статусом admin up
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[2]])

    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

    for intf in intf_to_check:  # для каждого интерфейса
        telnet_session.sendline(f'display mac-address interface {interface_normal_view(intf[0])}')
        telnet_session.expect(f'{interface_normal_view(intf[0])}')
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(intf[1])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n    {separator_str}\n'
        while True:
            match = telnet_session.expect(['  ---  ', "  ---- More ----", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8'))
            mac_output += page.strip()
            if match == 0:
                break
            elif match == 1:
                telnet_session.send(" ")
                mac_output += '\n'
            else:
                print("    Ошибка: timeout")
                break
        mac_output += '\n\n'
    return mac_output


def show_interfaces(telnet_session, huawei_type: str = 'huawei-1', privileged: bool = False) -> tuple:
    """
        Обнаруживаем интерфейсы на коммутаторе типа Huawei
    :param telnet_session:  залогиненная сессия
    :param huawei_type:     тип huawei: huawei-1, huawei-2 (по умолчанию huawei-1)
    :param privileged:      привелигированный ']' или нет '>' (по умолчанию нет)
    :return:                Кортеж (список интерфейсов, тип huawei)
    """
    template_type = ''
    output = ''

    if '1' in huawei_type:  # with '*down'
        telnet_session.sendline("display interface description")
        telnet_session.expect('display interface description')

    elif '2' in huawei_type:
        telnet_session.sendline('dis brief int')
        template_type = '2'

    while True:
        match = telnet_session.expect(['Too many parameters|Wrong parameter', ']', "  ---- More ----",
                                      "Unrecognized command", ">", pexpect.TIMEOUT])
        output += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        if match == 4 or match == 1:
            break
        elif match == 2:
            telnet_session.send(" ")
            output += '\n\n'
        elif match == 0 or match == 3:
            # Если непривилегированный пользователь
            if not privileged:
                telnet_session.expect('>')
                telnet_session.sendline('super')
                if not telnet_session.expect(['[Pp]ass', '<\S+>']):
                    telnet_session.sendline('sevaccess')
                    telnet_session.expect('>')
            telnet_session.sendline('dis brief int')
            telnet_session.expect('dis brief int')
            output = ''
            huawei_type = 'huawei-2'
            template_type = '2'
        else:
            print("    Ошибка: timeout")
            break

    with open(f'{root_dir}/templates/int_des_huawei{template_type}.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return [line for line in result if not line[0].startswith('NULL') and not line[0].startswith('V')], huawei_type


def show_device_info(telnet_session):
    version = '\n'
    huawei_type = 'huawei-1'
    telnet_session.sendline('display cpu')
    v = telnet_session.expect(['<', 'Unrecognized command', '  ---- More ----'])
    if v == 1:
        huawei_type = 'huawei-2'
        telnet_session.sendline('super')
        telnet_session.expect('[Pp]assword:')
        telnet_session.sendline('sevaccess')
        telnet_session.expect('>')
    elif v == 2:
        telnet_session.sendline('q')

    # VERSION
    telnet_session.sendline('display version')
    telnet_session.expect('display version')
    telnet_session.expect('\S+>')
    version += str(telnet_session.before.decode('utf-8')).replace(
        "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
    version += '\n\n\n'

    if huawei_type == 'huawei-2':
        # CPU
        telnet_session.sendline('display cpu')
        telnet_session.expect('display cpu')
        telnet_session.expect('<')
        version += '   ┌──────────────┐\n'
        version += '   │ ЗАГРУЗКА CPU │\n'
        version += '   └──────────────┘\n'
        version += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        version += '\n\n\n'

        # MANUINFO
        telnet_session.sendline('display device manuinfo')
        telnet_session.expect('display device manuinfo')
        telnet_session.expect('<')
        version += '   ┌───────────────────────────┐\n'
        version += '   │ MAC адрес, Серийный номер │\n'
        version += '   └───────────────────────────┘\n'
        version += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        version += '\n\n\n'

        # DHCP SNOOPING
        telnet_session.sendline('display dhcp-snooping')
        telnet_session.expect('display dhcp-snooping')
        version += '   ┌───────────────┐\n'
        version += '   │ DHCP SNOOPING │\n'
        version += '   └───────────────┘\n'
        dhcp_output = ''
        while True:
            match = telnet_session.expect(['<\S+>', "  ---- More ----", pexpect.TIMEOUT])
            dhcp_output += str(telnet_session.before.decode('utf-8')).replace(
                "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
            if match == 1:
                telnet_session.sendline(' ')
                dhcp_output += '\n '
            else:
                break
        version += dhcp_output
        version += '\n\n\n'

    if huawei_type == 'huawei-1':
        # MAC
        telnet_session.sendline('display bridge mac-address')
        telnet_session.expect('display bridge mac-address')
        telnet_session.expect('<')
        version += '   ┌───────────┐\n'
        version += '   │ MAC адрес │\n'
        version += '   └───────────┘\n'
        version += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        version += '\n\n\n'

        # TEMPERATURE
        telnet_session.sendline('display environment')
        telnet_session.expect('display environment')
        telnet_session.expect('<')
        version += '   ┌─────────────┐\n'
        version += '   │ Температура │\n'
        version += '   └─────────────┘\n'
        version += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        version += '\n\n\n'

        # FANS
        telnet_session.sendline('display fan verbose')
        telnet_session.expect('display fan verbose')
        telnet_session.expect('<')
        version += '   ┌────────────┐\n'
        version += '   │ Охлаждение │\n'
        version += '   └────────────┘\n'
        version += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        version += '\n\n\n'

        # E-LABEL
        telnet_session.sendline('display elabel')
        telnet_session.expect('display elabel')
        version += '\n' \
                   ' ┌                                    ┐\n' \
                   ' │ Расширенная техническая информация │\n' \
                   ' └                                    ┘\n' \
                   '                   ▼\n\n'
        while True:
            m = telnet_session.expect(['  ---- More ----', '<\S+>', pexpect.TIMEOUT])
            version += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
            if m == 0:
                telnet_session.sendline(' ')
                version += '\n'
            else:
                break
        version += '\n\n\n'
    return version


def show_cable_diagnostic(telnet_session):
    cable_diagnostic = ''
    telnet_session.sendline('system-view')
    v = telnet_session.expect(['\S+]$', 'Unrecognized command'])
    if v == 1:
        huawei_type = 'huawei-2'
        telnet_session.sendline('super')
        telnet_session.expect('[Pp]assword:')
        telnet_session.sendline('sevaccess')
        telnet_session.expect('>')
        telnet_session.sendline('system-view')
        telnet_session.expect('\S+]$')
    else:
        huawei_type = 'huawei-1'

    if huawei_type == 'huawei-1':
        # CABLE DIAGNOSTIC
        cable_diagnostic = '''
            ┌─────────────────────┐
            │ Диагностика кабелей │
            └─────────────────────┘

    Pair A/B/C/D   Четыре пары в сетевом кабеле

    Pair length    Длина сетевого кабеля:
                    ─ расстояние между интерфейсом и точкой разлома в случае возникновения неисправности;
                    ─ фактическая длина кабеля, когда он работает правильно.

    Pair state     Состояние сетевого кабеля:
                      Ok: указывает, что пара цепей нормально завершена.
                      Open: указывает, что пара цепей не завершена.
                      Short: указывает на короткое замыкание пары цепей.
                      Crosstalk: указывает на то, что пары цепей мешают друг другу.
                      Unknown: указывает, что пара цепей имеет неизвестную неисправность.


        '''
        interfaces_list, _ = show_interfaces(telnet_session=telnet_session)
        telnet_session.sendline('system-view')
        telnet_session.expect('\S+]$')
        for intf in interfaces_list:
            if 'NULL' not in intf[0] and 'Vlan' not in intf[0]:
                try:
                    separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}')
                    cable_diagnostic += f'    Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}\n' \
                                        f'    {separator_str}\n'
                    telnet_session.sendline(f'interface {interface_normal_view(intf[0])}')
                    telnet_session.expect(f'\S+]$')
                    telnet_session.sendline('virtual-cable-test')
                    if telnet_session.expect(['continue \[Y/N\]', 'Error:']):
                        cable_diagnostic += 'Данный интерфейс не поддерживается\n\n'
                        telnet_session.sendline('quit')
                        telnet_session.expect('\S+]$')
                        continue
                    telnet_session.sendline('Y')
                    telnet_session.expect('\?Y\W*')
                    telnet_session.expect('\[\S+\]$')
                    cable_diagnostic += str(telnet_session.before.decode('utf-8'))
                    cable_diagnostic += '\n'
                    telnet_session.sendline('quit')
                    telnet_session.expect(f'\S+]$')
                except pexpect.TIMEOUT:
                    break

    if huawei_type == 'huawei-2':
        # CABLE DIAGNOSTIC
        cable_diagnostic = '''
                ┌─────────────────────┐
                │ Диагностика кабелей │
                └─────────────────────┘


'''
        interfaces_list, _ = show_interfaces(telnet_session=telnet_session,
                                             huawei_type='huawei-2',
                                             privileged=True)
        for intf in interfaces_list:
            if 'NULL' not in intf[0] and 'Vlan' not in intf[0] and not 'SVSL' in intf[2]:
                try:
                    separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}')
                    cable_diagnostic += f'    Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}\n' \
                                        f'    {separator_str}\n'
                    telnet_session.sendline(f'interface {interface_normal_view(intf[0])}')
                    telnet_session.expect(f'\S+]$')
                    telnet_session.sendline('virtual-cable-test')
                    telnet_session.expect('virtual-cable-test\W+')
                    telnet_session.expect('\[\S+\d\]$')
                    cable_diagnostic += str(telnet_session.before.decode('utf-8'))
                    cable_diagnostic += '\n'
                    telnet_session.sendline('quit')
                    telnet_session.expect(f'\S+]$')

                except pexpect.TIMEOUT:
                    break
    return cable_diagnostic


def show_vlans(telnet_session, interfaces, device_type: str = 'huawei-1') -> tuple:
    result = []
    for line in interfaces:
        if not line[0].startswith('V') and not line[0].startswith('NU') and not line[0].startswith('A'):
            telnet_session.sendline(f"display current-configuration interface {interface_normal_view(line[0])}")
            # telnet_session.expect(f"interface {interface_normal_view(line[0])}")
            output = ''
            while True:
                match = telnet_session.expect([r'>', "  ---- More ----", pexpect.TIMEOUT])
                page = str(telnet_session.before.decode('utf-8'))
                output += page.strip()
                if match == 0:
                    break
                elif match == 1:
                    telnet_session.send(" ")
                    output += '\n'
                else:
                    print("    Ошибка: timeout")
                    break
            vlans_group = sub('(?<=undo).+vlan (.+)', '', output)   # Убираем строчки, где есть "undo"
            vlans_group = list(set(findall(r'vlan (.+)', vlans_group)))   # Ищем строчки вланов, без повторений
            switchport_mode = list(set(findall(r'port (hybrid|trunk|access)', output)))  # switchport mode
            max_letters_in_string = 35  # Ограничение на кол-во символов в одной строке в столбце VLAN's
            vlans_compact_str = ''      # Строка со списком VLANов с переносами
            line_str = ''
            for part in ','.join(switchport_mode + vlans_group).split(','):
                if len(line_str) + len(part) <= max_letters_in_string:
                    line_str += f'{part},'
                else:
                    vlans_compact_str += f'{line_str}\n'
                    line_str = f'{part},'
            else:
                vlans_compact_str += line_str[:-1]
            # print(line + [vlans_compact_str])
            result.append(line + [vlans_compact_str])

    if device_type == 'huawei-1':
        telnet_session.sendline(f"display vlan")
        telnet_session.expect(r"VID\s+Status\s+Property")
    else:
        telnet_session.sendline(f"display vlan all")
        telnet_session.expect(f"display vlan all")

    vlans_info = ''
    while True:
        match = telnet_session.expect([r'>', "  ---- More ----", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8'))
        vlans_info += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            vlans_info += '\n'
        else:
            print("    Ошибка: timeout")
            break

    with open(f'{root_dir}/templates/vlans_templates/{device_type}_vlan_info.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
