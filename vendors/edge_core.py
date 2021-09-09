from re import findall
import sys
import textfsm
from core.misc import interface_normal_view
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, prompt: str = r'\S+#$', next_catch: str = None):
    return sendcmd(session, command, prompt, space_prompt='---More---', before_catch=next_catch)


def show_interfaces(session) -> list:
    output = send_command(
        session=session,
        command='show running-config',
    )

    des_output = send_command(
        session=session,
        command='show interfaces status'
    )
    with open(f'{sys.path[0]}/templates/interfaces/edge_core.template', 'r') as template_file:
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
                [
                    interface,
                    link_stat.lower() if admin_status == 'up' else admin_status,
                    description
                ]
            )
    return result


def show_device_info(session):
    # VERSION
    system_info = send_command(
        session=session,
        command='show system'
    )
    version = send_command(
        session=session,
        command='show version'
    )

    info = f'{system_info}\n{version}'
    return info


def show_mac(session, interfaces: list, desc_filter: str):
    mac_output = ''  # Вывод MAC

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for interface in intf_to_check:
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(interface[1])}')
        mac_output += f'\n\n    Интерфейс: {interface_normal_view(interface[1])}\n' \
                      f'    {separator_str}\n'
        mac_output += send_command(
            session=session,
            command=f'show mac-address-table interface {interface_normal_view(interface[0])}'
        )
    return mac_output


def show_vlan(session, interfaces: list):
    result = []
    running_config = send_command(
        session=session,
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
        session=session,
        command='show vlan'
    )
    with open(f'{sys.path[0]}/templates/vlans_templates/edge_core.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlan_info)  # Ищем интерфейсы
    return vlans_info_table, result
