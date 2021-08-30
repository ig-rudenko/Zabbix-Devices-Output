import pexpect
from re import findall, sub
import sys
import textfsm
from core.misc import interface_normal_view
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, prompt: str = r'\S+#$', next_catch: str = None):
    return sendcmd(session, command, prompt, space_prompt="--More--", before_catch=next_catch)


def show_mac(telnet_session, interfaces: list, interface_filter: str) -> str:
    mac_output = ''  # Вывод MAC

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for intf in intf_to_check:  # для каждого интерфейса
        telnet_session.sendline(f'show mac-address-table interface ethernet {intf[0]}')
        telnet_session.expect(f'Read mac address table....')
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(intf[1])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n' \
                      f'    {separator_str}\n'
        while True:
            match = telnet_session.expect([r'#$', " --More-- ", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                "        ", '')
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


def show_interfaces(telnet_session) -> list:
    output = send_command(
        session=telnet_session,
        command='show interface ethernet status'
    )
    output = sub(r'[\W\S]+\nInterface', '\nInterface', output)
    with open(f'{sys.path[0]}/templates/interfaces/q-tech.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return result


def show_device_info(telnet_session):
    info = ''
    # VERSION
    info += send_command(
        session=telnet_session,
        command='show version'
    )

    # TEMPERATURE
    info += '   ┌─────────────┐\n'
    info += '   │ Температура │\n'
    info += '   └─────────────┘\n'
    info += send_command(
        session=telnet_session,
        command='show temperature'
    )

    # FANS
    info += '   ┌──────┐\n'
    info += '   │ FANS │\n'
    info += '   └──────┘\n'
    info += send_command(
        session=telnet_session,
        command='show fan'
    )

    # SNMP
    info += '   ┌──────┐\n'
    info += '   │ SNMP │\n'
    info += '   └──────┘\n'
    info += send_command(
        session=telnet_session,
        command='show snmp status'
    )

    return info


def show_vlan(telnet_session, interfaces):
    result = []
    for line in interfaces:
        if not line[0].startswith('V'):
            output = send_command(
                session=telnet_session,
                command=f"show running-config interface ethernet {line[0]}"
            )
            vlans_group = findall(r'vlan [add ]*(\S*\d)', output)  # Строчки вланов
            switchport_mode = findall(r'switchport mode (\S+)', output)  # switchport mode
            max_letters_in_string = 20  # Ограничение на кол-во символов в одной строке в столбце VLAN's
            vlans_compact_str = ''  # Строка со списком VLANов с переносами
            line_str = ''
            for part in set(';'.join(switchport_mode + vlans_group).split(';')):
                if len(line_str) + len(part) <= max_letters_in_string:
                    line_str += f'{part},'
                else:
                    vlans_compact_str += f'{line_str}\n'
                    line_str = f'{part},'
            else:
                vlans_compact_str += line_str[:-1]

            result.append(line + [vlans_compact_str])

    vlans_info = send_command(
        session=telnet_session,
        command='show vlan'
    )
    with open(f'{sys.path[0]}/templates/vlans_templates/q-tech.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
