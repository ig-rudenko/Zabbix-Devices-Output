import pexpect
from re import findall, sub
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_interfaces(telnet_session, eltex_type: str = 'mes') -> str:
    telnet_session.sendline("show int des")
    telnet_session.expect("show int des")
    output = ''
    while True:
        match = telnet_session.expect([r'\S+#', "More: <space>", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '')
        output += page.strip()
        if 'Ch       Port Mode (VLAN)' in output:
            telnet_session.sendline('q')
            telnet_session.expect('#')
            break
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/int_des_{eltex_type}.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return result


def show_mac_esr_12vf(telnet_session) -> str:
    # Для Eltex ESR-12VF выводим всю таблицу MAC адресов
    mac_output = ''
    telnet_session.sendline(f'show mac address-table ')
    telnet_session.expect('# ')
    m_output = sub('.+\nVID', 'VID', str(telnet_session.before.decode('utf-8')))
    mac_output += f"\n{m_output}"
    return mac_output


def show_mac_mes(telnet_session, interfaces: list, interface_filter: str) -> str:
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
        separator_str = '─' * len(f'Интерфейс: {intf[1]}')
        mac_output += f'\n    Интерфейс: {intf[1]}\n    {separator_str}\n'
        telnet_session.expect(r'Aging time is \d+ \S+')

        while True:
            match = telnet_session.expect([r'#$', "More: <space>", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                "        ", '').replace('[0m', '')
            mac_output += f"    {page.strip()}"
            if match == 0:
                break
            elif match == 1:
                telnet_session.expect('<return>')
                telnet_session.send(" ")
            else:
                print("    Ошибка: timeout")
                break
        mac_output = sub('SVSL.+', '', mac_output)
        mac_output = sub(r'(?<=\d)(?=\S\S:\S\S:\S\S:\S\S:\S\S:\S\S)', r'     ', mac_output)
        mac_output = sub(r'Vlan\s+Mac\s+Address\s+Port\s+Type',
                         'Vlan          Mac_Address         Port       Type',
                         mac_output)
        mac_output += '\n'
    return mac_output


def show_device_info(telnet_session):
    info = ''

    # SYSTEM ID
    telnet_session.sendline('show system id')
    telnet_session.expect('show system id\W+')
    telnet_session.expect('\W+\S+#')
    info += telnet_session.before.decode('utf-8')
    info += '\n\n'

    # VERSION
    telnet_session.sendline('show system')
    telnet_session.expect('show system')
    telnet_session.expect('\W+\S+#')
    info += telnet_session.before.decode('utf-8')
    info += '\n\n'

    # CPU
    telnet_session.sendline('show cpu utilization')
    telnet_session.expect('show cpu utilization')
    telnet_session.expect('\S+#')
    info += '   ┌──────────────┐\n'
    info += '   │ ЗАГРУЗКА CPU │\n'
    info += '   └──────────────┘\n'
    info += telnet_session.before.decode('utf-8')
    info += '\n\n'

    # SNMP
    telnet_session.sendline('show snmp')
    telnet_session.expect('show snmp\W+')
    telnet_session.expect('\W+\S+#$')
    info += '   ┌──────┐\n'
    info += '   │ SNMP │\n'
    info += '   └──────┘\n'
    info += telnet_session.before.decode('utf-8')
    info += '\n\n'
    return info


def show_vlans(telnet_session, interfaces) -> tuple:
    result = []
    for line in interfaces:
        if not line[0].startswith('V'):
            telnet_session.sendline(f"show running-config interface {interface_normal_view(line[0])}")
            telnet_session.expect(f"interface {interface_normal_view(line[0])}")
            output = ''
            while True:
                match = telnet_session.expect([r'#', "More: <space>", pexpect.TIMEOUT])
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

    telnet_session.sendline(f"show vlan")
    telnet_session.expect("show vlan")
    vlans_info = ''
    while True:
        match = telnet_session.expect([r'#', "More: <space>", pexpect.TIMEOUT])
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

    with open(f'{root_dir}/templates/vlans_templates/eltex_vlan_info.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
