import sys
import textfsm
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, prompt: str = r'\S+\s*#\s*$', next_catch: str = None) -> str:
    return sendcmd(session, command, prompt, space_prompt="Press <SPACE> to continue or <Q> to quit:", before_catch=next_catch)


def show_mac(telnet_session, interfaces: list, interface_filter: str) -> str:
    mac_output = ''  # Вывод MAC

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for intf in intf_to_check:  # для каждого интерфейса
        separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
        mac_output += f'\n\n    Интерфейс: {intf[0]} ({intf[1]})\n' \
                      f'    {separator_str}\n'

        mac_output_ = send_command(
            session=telnet_session,
            command=f'show fdb ports {intf[0]}'
        )
        cut = mac_output_.find('Flags : d -')
        mac_output += mac_output_[:cut]

    return mac_output


def show_interfaces(telnet_session) -> list:
    # LINKS
    output_links = send_command(
        session=telnet_session,
        command='show ports information'
    )
    with open(f'{sys.path[0]}/templates/interfaces/extreme_links.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_state = int_des_.ParseText(output_links)  # Ищем интерфейсы
    for position, line in enumerate(result_port_state):
        if result_port_state[position][1].startswith('D'):
            result_port_state[position][1] = 'Disable'
        elif result_port_state[position][1].startswith('E'):
            result_port_state[position][1] = 'Enable'
        else:
            result_port_state[position][1] = 'None'

    # DESC
    output_des = send_command(
        session=telnet_session,
        command='show ports description'
    )

    with open(f'{sys.path[0]}/templates/interfaces/extreme_des.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_des = int_des_.ParseText(output_des)  # Ищем desc

    result = [result_port_state[n] + result_des[n] for n in range(len(result_port_state))]
    return [
        [
            line[0],    # interface
            line[2].replace('ready', 'down').replace('active', 'up') if 'Enabled' in line[1] else 'admin down', # status
            line[3]     # desc
        ]
        for line in result
    ]


def show_device_info(telnet_session):
    info = '\n'

    # VERSION
    info += send_command(
        session=telnet_session,
        command='show switch detail'
    )

    info += send_command(
        session=telnet_session,
        command='show version detail'
    )

    info += '           ┌────────────┐\n' \
            '           │ Охлаждение │\n' \
            '           └────────────┘\n'

    info += send_command(
        session=telnet_session,
        command='show fans detail'
    )

    # TEMPERATURE
    info += '           ┌─────────────┐\n' \
            '           │ Температура │\n' \
            '           └─────────────┘\n'
    info += send_command(
        session=telnet_session,
        command='show temperature'
    )

    # POWER
    info += '           ┌─────────┐\n' \
            '           │ Питание │\n' \
            '           └─────────┘\n'
    info += send_command(
        session=telnet_session,
        command='show power'
    )

    info += ' ┌                                    ┐\n' \
            ' │ Расширенная техническая информация │\n' \
            ' └                                    ┘\n' \
            '                   ▼\n\n' \
            '           ┌───────────────┐\n' \
            '           │ Platform Info │\n' \
            '           └───────────────┘\n'
    # PLATFORM INFORMATION
    info += send_command(
        session=telnet_session,
        command='debug hal show platform platformInfo'
    )
    # SLOTS
    info += '           ┌───────┐\n' \
            '           │ Слоты │\n' \
            '           └───────┘\n'
    info += send_command(
        session=telnet_session,
        command='debug hal show platform deviceInfo'
    )
    return info


def show_vlans(telnet_session, interfaces: list):

    def range_to_numbers(ports_string: str) -> list:
        ports_split = ports_string.replace(' ', '').split(',')
        res_ports = []
        for p in ports_split:
            if '-' in p:
                port_range = list(range(int(p.split('-')[0]), int(p.split('-')[1]) + 1))
                for pr in port_range:
                    res_ports.append(int(pr))
            else:
                res_ports.append(int(p))

        return sorted(res_ports)

    output_vlans = send_command(
        session=telnet_session,
        command='show configuration "vlan"',
        next_catch=r'Module vlan configuration\.'
    )

    with open(f'{sys.path[0]}/templates/vlans_templates/extreme.template', 'r') as template_file:
        vlan_templ = textfsm.TextFSM(template_file)
        result_vlans = vlan_templ.ParseText(output_vlans)

    # Создаем словарь, где ключи это кол-во портов, а значениями будут вланы на них
    ports_vlan = {num: [] for num in range(1, len(interfaces) + 1)}

    for vlan in result_vlans:
        for port in range_to_numbers(vlan[1]):
            # Добавляем вланы на порты
            ports_vlan[port].append(vlan[0])
    interfaces_vlan = []  # итоговый список (интерфейсы и вланы)

    for line in interfaces:
        max_letters_in_string = 20  # Ограничение на кол-во символов в одной строке в столбце VLAN's
        vlans_compact_str = ''  # Строка со списком VLANов с переносами
        line_str = ''
        for part in ports_vlan[int(line[0])]:
            if len(line_str) + len(part) <= max_letters_in_string:
                line_str += f'{part},'
            else:
                vlans_compact_str += f'{line_str}\n'
                line_str = f'{part},'
        else:
            vlans_compact_str += line_str[:-1]
        # Итоговая строка: порт, статус, описание + вланы
        interfaces_vlan.append(line + [vlans_compact_str])

    # Описание VLAN'ов
    with open(f'{sys.path[0]}/templates/vlans_templates/extreme_vlan_info.template', 'r') as template_file:
        vlan_templ = textfsm.TextFSM(template_file)
        vlans_info = vlan_templ.ParseText(output_vlans)
    vlans_info = sorted(vlans_info, key=lambda line: int(line[0]))  # Сортировка по возрастанию vlan
    return vlans_info, interfaces_vlan
