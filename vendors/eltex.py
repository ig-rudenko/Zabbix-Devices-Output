import pexpect
from re import findall, sub
import sys
import textfsm
from core.misc import interface_normal_view
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, prompt: str = r'\S+#\s*$', next_catch: str = None):
    return sendcmd(session, command, prompt, space_prompt=r"More: <space>,  Quit: q or CTRL\+Z, One line: <return> ",
                   before_catch=next_catch)


def show_interfaces(session, eltex_type: str = 'eltex-mes') -> str:
    session.sendline("show int des")
    session.expect("show int des")
    output = ''
    while True:
        match = session.expect(
            [
                r'\S+#\s*$',
                r"More: <space>,  Quit: q or CTRL\+Z, One line: <return> ",
                pexpect.TIMEOUT
            ]
        )
        output += session.before.decode('utf-8').strip()
        if 'Ch       Port Mode (VLAN)' in output:
            session.sendline('q')
            session.expect(r'\S+#\s*$')
            break
        if match == 0:
            break
        elif match == 1:
            session.send(" ")
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{sys.path[0]}/templates/interfaces/{eltex_type}.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return result


def show_mac(session, interfaces: list, interface_filter: str, eltex_type: str = 'eltex-mes') -> str:
    mac_output = ''

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for intf in intf_to_check:  # для каждого интерфейса
        separator_str = '─' * len(f'Интерфейс: {intf[1]}')
        mac_output += f'\n    Интерфейс: {intf[1]}\n    {separator_str}\n'

        if 'eltex-mes' in eltex_type:
            session.sendline(f'show mac address-table interface {interface_normal_view(intf[0])}')
            session.expect(r'Aging time is \d+ \S+')
            while True:
                match = session.expect(
                    [
                        r'\S+#\s*$',
                        r"More: <space>,  Quit: q or CTRL\+Z, One line: <return> ",
                        pexpect.TIMEOUT
                    ]
                )
                page = session.before.decode('utf-8')
                mac_output += f"    {page.strip()}"
                if match == 0:
                    break
                elif match == 1:
                    session.send(" ")
                else:
                    print("    Ошибка: timeout")
                    break
            mac_output = sub(r'(?<=\d)(?=\S\S:\S\S:\S\S:\S\S:\S\S:\S\S)', r'     ', mac_output)
            mac_output = sub(r'Vlan\s+Mac\s+Address\s+Port\s+Type',
                             'Vlan          Mac_Address         Port       Type',
                             mac_output)
            mac_output += '\n'

        if 'eltex-esr' in eltex_type:
            mac_output += "VID     MAC Address          Interface                        Type \n" \
                          "-----   ------------------   ------------------------------   -------"
            mac_output += send_command(
                session=session,
                command=f'show mac address-table interface {interface_normal_view(intf[0])} |'
                        f' include \"{interface_normal_view(intf[0]).lower()}\"'
            )

    return mac_output


def show_device_info(session):
    info = ''

    # SYSTEM ID
    session.sendline('show system id')
    session.expect(r'show system id\W+')
    session.expect(r'\W+\S+#')
    info += session.before.decode('utf-8')
    info += '\n\n'

    # VERSION
    session.sendline('show system')
    session.expect(r'show system')
    session.expect(r'\W+\S+#')
    info += session.before.decode('utf-8')
    info += '\n\n'

    # CPU
    session.sendline('show cpu utilization')
    session.expect(r'show cpu utilization')
    session.expect(r'\S+#')
    info += '   ┌──────────────┐\n'
    info += '   │ ЗАГРУЗКА CPU │\n'
    info += '   └──────────────┘\n'
    info += session.before.decode('utf-8')
    info += '\n\n'

    # SNMP
    session.sendline('show snmp')
    session.expect(r'show snmp\W+')
    session.expect(r'\W+\S+#$')
    info += '   ┌──────┐\n'
    info += '   │ SNMP │\n'
    info += '   └──────┘\n'
    info += session.before.decode('utf-8')
    info += '\n\n'
    return info


def show_vlans(session, interfaces) -> tuple:
    result = []
    for line in interfaces:
        if not line[0].startswith('V'):
            output = send_command(
                session=session,
                command=f'show running-config interface {interface_normal_view(line[0])}'
            )
            vlans_group = findall(r'vlan [add ]*(\S*\d)', output)   # Строчки вланов
            switchport_mode = findall(r'switchport mode (\S+)', output)  # switchport mode
            max_letters_in_string = 20  # Ограничение на кол-во символов в одной строке в столбце VLAN's
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

    vlans_info = send_command(
        session=session,
        command='show vlan'
    )

    with open(f'{sys.path[0]}/templates/vlans_templates/eltex_vlan_info.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
