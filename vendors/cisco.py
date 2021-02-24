import pexpect
from re import findall, sub
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_mac(telnet_session, interfaces: list, interface_filter: str) -> str:

    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    not_uplinks = True if interface_filter == 'only-abonents' else False

    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[3].upper() and  # - интерфейсов, которые содержат "SVSL"
                    'POWER_MONITORING' not in line[3].upper())  # - POWER_MONITORING
                and not ('down' in line[2].lower() and not line[3])  # - пустые интерфейсы с LinkDown
                and 'down' not in line[1].lower()  # И только интерфейсы со статусом admin up
                and 'VL' not in line[0].upper()  # И не VLAN'ы
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[3]])

    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

    for intf in intf_to_check:  # для каждого интерфейса
        telnet_session.sendline(f'show mac address-table interface {interface_normal_view(intf[0])}')
        telnet_session.expect(f'-------------------')
        telnet_session.expect('Vla')
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(intf[1])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n' \
                      f'    {separator_str}\n' \
                      f'Vla'
        while True:
            match = telnet_session.expect(['Total Mac Addresses', r'#$', "--More--", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                "        ", '')
            mac_output += page.strip()
            if match <= 1:
                break
            elif match == 2:
                telnet_session.send(" ")
                mac_output += '\n'
            else:
                print("    Ошибка: timeout")
                break
        mac_output += '\n\n'
    return mac_output


def show_interfaces(telnet_session) -> list:
    telnet_session.sendline("show int des")
    telnet_session.expect("show int des")
    output = ''
    while True:
        match = telnet_session.expect([r'\S+#$', "--More--", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '')
        output += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            output += '\n'
        else:
            print("    Ошибка: timeout")
            break
    output = sub('.+\nInterface', 'Interface', output)
    with open(f'{root_dir}/templates/int_des_cisco.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы

    return [line for line in result if not line[0].startswith('V')]


def show_device_info(telnet_session):
    version = ''
    # VERSION
    telnet_session.sendline('show version')
    telnet_session.expect('show version')
    while True:
        match = telnet_session.expect([r'\S+#$', "--More--", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '')
        version += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            version += '\n'
        else:
            print("    Ошибка: timeout")
            break
    version = sub(r'\W+This product [\W\S]+cisco\.com\.', '', version)
    version += '\n'

    # ENVIRONMENT
    telnet_session.sendline('show environment')
    telnet_session.expect('show environment')
    version += '   ┌──────────────────────────────────┐\n'
    version += '   │ Температура, Питание, Охлаждение │\n'
    version += '   └──────────────────────────────────┘\n'
    while True:
        m = telnet_session.expect([' --More-- ', '\S+#$'])
        env_str = str(telnet_session.before.decode('utf-8'))
        if 'Invalid input' in env_str:
            version += 'Нет данных\n'
        else:
            version += env_str
        if m == 0:
            telnet_session.sendline(' ')
        else:
            break

    # INVENTORY
    telnet_session.sendline('show inventory oid')
    telnet_session.expect('show inventory oid')
    version += '   ┌────────────────┐\n'
    version += '   │ Инвентаризация │\n'
    version += '   └────────────────┘\n'
    while True:
        m = telnet_session.expect([' --More-- ', '\S+#$', 'Invalid input|% No entity'])
        version += str(telnet_session.before.decode('utf-8'))
        if m == 0:
            telnet_session.sendline(' ')
        elif m == 2:    # Если нет ключа "oid"
            telnet_session.sendline('show inventory')
            telnet_session.expect('show inventory')
        else:
            break

    # SNMP
    telnet_session.sendline('show snmp')
    telnet_session.expect('show snmp')
    telnet_session.expect('\S+#$')
    version += '   ┌──────┐\n'
    version += '   │ SNMP │\n'
    version += '   └──────┘\n'
    version += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "        ", '')

    # IDPROMs
    telnet_session.sendline('show idprom all')
    telnet_session.expect('show idprom all')
    tech_info = '\n' \
                ' ┌                                    ┐\n' \
                ' │ Расширенная техническая информация │\n' \
                ' └                                    ┘\n' \
                '                   ▼\n\n'
    while True:
        match = telnet_session.expect([r'\S+#$', "--More--", '% Invalid input', pexpect.TIMEOUT])
        if match == 2:
            tech_info = ''
            break
        tech_info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '').strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            tech_info += '\n'
        else:
            print("    Ошибка: timeout")
            break
    version += tech_info
    return version


def show_vlans(telnet_session, interfaces) -> tuple:
    result = []
    for line in interfaces:
        if not line[0].startswith('V'):
            telnet_session.sendline(f"show running-config interface {interface_normal_view(line[0])}")
            telnet_session.expect("Building configuration..")
            output = ''
            while True:
                match = telnet_session.expect([r'\S+#$', "--More--", pexpect.TIMEOUT])
                page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                    "        ", '')
                output += page.strip()
                if match == 0:
                    break
                elif match == 1:
                    telnet_session.send(" ")
                    output += '\n'
                else:
                    print("    Ошибка: timeout")
                    break
            vlans_group = findall(r'vlan [add ]*(\S*\d)', output)   # Строчки вланов
            switchport_mode = findall(r'switchport mode (\S+)', output)  # switchport mode
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

            result.append(line + [vlans_compact_str])

    telnet_session.sendline(f"show vlan brief")
    telnet_session.expect("show vlan brief")
    vlans_info = ''
    while True:
        match = telnet_session.expect([r'\S+#$', "--More--", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '')
        vlans_info += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            vlans_info += '\n'
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/vlans_templates/cisco_vlan_info.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
