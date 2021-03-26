import pexpect
from re import findall
import sys
from core import textfsm
from core.intf_view import interface_normal_view

root_dir = sys.path[0]


def send_command(session, command: str, prompt: str = r'\S+#$', next_catch: str = None):
    session.sendline(command)
    session.expect(command[-30:])
    if next_catch:
        session.expect(next_catch)
    output = ''
    while True:
        match = session.expect(
            [
                '---More---',
                prompt,
                pexpect.TIMEOUT
            ]
        )
        output += str(session.before.decode('utf-8')).replace(
            '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08',
            '').strip()
        if match == 0:
            session.sendline(' ')
            output += '\n'
        elif match == 1:
            break
        else:
            print("    Ошибка: timeout")
            break
    return output


def show_interfaces(telnet_session) -> list:
    output = send_command(
        session=telnet_session,
        command='show running-config',
    )

    des_output = send_command(
        session=telnet_session,
        command='show interfaces status'
    )
    with open(f'{root_dir}/templates/int_des_edge_core.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_des = int_des_.ParseText(des_output)  # Ищем интерфейсы

    result = []
    intf_raw = findall(r'(interface (.+\n)+?!)', str(output))
    for x in intf_raw:
        interface = findall(r'interface (\S*\s*\S*\d)', str(x))[0]
        admin_status = 'admin down' if 'shutdown' in str(x) else 'up'
        description = findall(r'description (\S+?(?=\\|\s))', str(x))[0] if len(
            findall(r'description (\S+)', str(x))) > 0 else ''
        for line in result_des:
            if interface_normal_view(line[0]) == interface_normal_view(interface):
                link_stat = line[3]
                break
        else:
            link_stat = 'Down'
        if 'VLAN' not in interface:
            result.append(
                [interface, admin_status, link_stat, description]
            )
    return result


def show_device_info(telnet_session):
    # VERSION
    system_info = send_command(
        session=telnet_session,
        command='show system'
    )
    version = send_command(
        session=telnet_session,
        command='show version'
    )

    info = f'{system_info}\n{version}'
    return info


def show_mac(telnet_session, interfaces: list, desc_filter: str):
    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    not_uplinks = True if desc_filter == 'only-abonents' else False

    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(desc_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[3].upper() and 'BOX' not in line[3].upper() and
                    # - интерфейсов, которые содержат "SVSL" или "box"
                    'POWER_MONITORING' not in line[3].upper())  # - НЕ POWER_MONITORING
                and not ('down' in line[2].lower() and not line[3])  # - пустые интерфейсы с LinkDown
                and 'down' not in line[1].lower()  # И только интерфейсы со статусом admin up
                and 'VL' not in line[0].upper()  # И не VLAN'ы
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[3]])
    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{desc_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'
    for interface in intf_to_check:
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(interface[1])}')
        mac_output += f'\n\n    Интерфейс: {interface_normal_view(interface[1])}\n' \
                      f'    {separator_str}\n'
        mac_output += send_command(
            session=telnet_session,
            command=f'show mac-address-table interface {interface_normal_view(interface[0])}'
        )
    return mac_output


def show_vlan(telnet_session, interfaces: list):
    result = []
    running_config = send_command(
        session=telnet_session,
        command='show running-config'
    )
    intf_from_config = findall(r'(interface (.+\n)+?!)', running_config)
    for line in interfaces:
        for intf in intf_from_config:
            interface = findall(r'interface (\S+\s\d+/\d+)', str(intf))
            if not interface:
                continue
            if not line[0].startswith('V') and line[0] == interface[0]:
                vlans_group = findall(r'VLAN add (\S+) tagged', str(intf))  # Строчки вланов
                max_letters_in_string = 20
                vlans_compact_str = ''  # Строка со списком VLANов с переносами
                line_str = ''
                for part in set(','.join(vlans_group).split(',')):
                    if len(line_str) + len(part) <= max_letters_in_string:
                        line_str += f'{part},'
                    else:
                        vlans_compact_str += f'{line_str}\n'
                        line_str = f'{part},'
                else:
                    vlans_compact_str += line_str[:-1]

                result.append(line + [vlans_compact_str])

    vlan_info = send_command(
        session=telnet_session,
        command='show vlan'
    )
    with open(f'{root_dir}/templates/vlans_templates/edge_core.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlan_info)  # Ищем интерфейсы
    return vlans_info_table, result
