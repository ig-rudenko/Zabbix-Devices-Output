import pexpect
import sys
import textfsm
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, next_catch=None):
    return sendcmd(session, command, prompt=r'\S+\(cfg\)#|\S+>', space_prompt="----- more -----",
                   before_catch=next_catch)


def show_interfaces(session) -> list:
    output = send_command(session, 'show port')
    with open(f'{sys.path[0]}/templates/interfaces/zte.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return [
        [
            line[0],    # interface
            line[2] if 'enabled' in line[1] else 'admin down',  # status
            line[3]     # desc
        ]
        for line in result
    ]


def show_mac(session, interfaces: list, interface_filter: str, model: str):
    mac_output = ''

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for intf in intf_to_check:
        if '2936-FI' in model:
            mac_command = f'show fdb port {intf[0]} detail'
            mac_expect = [r'MacAddress\s*Vlan\s*PortId\s*Type\W+-+\s*-+\s*-+\s*-+', 'No matching mac address']
            mc_output = '  MacAddress        Vlan  PortId   Type\n  '
        else:
            mac_command = f'show mac all-types port {intf[0]}'
            mac_expect = [r'6,DHCP', 'No MAC']
            mc_output = ''
        session.sendline(mac_command)
        session.expect(mac_command)
        if session.expect(mac_expect):   # нет MAC
            separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
            mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n  No MAC address exists!\n\n"
            continue

        while True:
            match = session.expect(
                [
                    r'\S+\(cfg\)#$|\S+>$',        # 0 - конец списка
                    r"\r\n----- more ----- Press Q or Ctrl\+C to break -----",     # 1 - далее
                    pexpect.TIMEOUT     # 2
                ]
            )
            page = str(session.before.decode('utf-8')).replace("[42D", '').replace(
                "        ", '').\
                replace(
                '                                                   '
                , '  '
            )
            mc_output += page.strip()
            if match == 0:
                break
            elif match == 1:
                session.send(" ")
                mc_output += '\n'
            else:
                print("    Ошибка: timeout")
                break

        separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
        mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n{mc_output}\n\n"
    if not intf_to_check:
        return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
    return mac_output


def show_device_info(session):

    def send_command(command: str):
        session.sendline(command)
        session.expect(command)
        session.expect(r'\S+\(cfg\)#$|\S+>$')
        return session.before.decode('utf-8').strip()

    device_info = f"""
    {send_command('show version')}
       ┌──────────────┐
       │ Загрузка CPU │
       └──────────────┘
    {send_command('show cpu')}
       ┌──────────────┐
       │  Охлаждение  │
       └──────────────┘
    {send_command('show fan')}
       ┌──────────────┐
       │   Сервисы    │
       └──────────────┘
    {send_command('show ssh')}

    {send_command('show web')}

    {send_command('show anti-DoS')}
       ┌──────────────┐
       │ USERS ONLINE │
       └──────────────┘
    {send_command('show user')}
    """
    return device_info


def get_vlans(session, interfaces: list):

    def range_to_numbers(ports_string: str) -> list:
        # print('port_string', ports_string)
        ports_split = ports_string.split(',')
        res_ports = []
        # print('ports_split', ports_split)
        if not ports_split[0]:
            return []

        for p in ports_split:
            if not p:
                continue
            if '-' in p:
                port_range = list(range(int(p.split('-')[0]), int(p.split('-')[1]) + 1))
                # print('port_range', port_range)
                for pr in port_range:
                    res_ports.append(int(pr))
            else:
                res_ports.append(int(p))

        return sorted(res_ports)

    output = send_command(session, 'show vlan')

    with open(f'{sys.path[0]}/templates/vlans_templates/zte_vlan.template', 'r') as template_file:
        vlan_templ = textfsm.TextFSM(template_file)
        result_vlan = vlan_templ.ParseText(output)
    # print(result_vlan)

    vlan_port = {}
    vlan_info = ''
    for vlan in result_vlan:
        # VLAN info
        if vlan[1].strip():
            vlan_info += f'VLAN {vlan[0]} {vlan[4] if vlan[4] == "disabled" else ""} ({vlan[1]})\n'
        else:
            vlan_info += f'VLAN {vlan[0]} {vlan[4] if vlan[4] == "disabled" else ""}\n'

        # VLAN ports
        # Если не нашли влан, или он деактивирован, то пропускаем
        if not vlan[0] or vlan[4] == "disabled":
            continue
        # print('\nvlan', vlan[0], vlan[1], vlan[2], vlan[3])
        # Объединяем тегированные вланы и нетегированные в один список
        vlan_port[int(vlan[0])] = range_to_numbers(','.join([vlan[2], vlan[3]]))

    interfaces_vlan = []  # итоговый список (интерфейсы и вланы)

    for line in interfaces:
        max_letters_in_string = 20  # Ограничение на кол-во символов в одной строке в столбце VLAN's
        vlans_compact_str = ''  # Строка со списком VLANов с переносами
        line_str = ''
        for vlan_id in vlan_port:
            if int(line[0]) in vlan_port[vlan_id]:
                if len(line_str) + len(str(vlan_id)) <= max_letters_in_string:
                    line_str += f'{vlan_id},'
                else:
                    vlans_compact_str += f'{line_str}\n'
                    line_str = f'{vlan_id},'
        else:
            vlans_compact_str += line_str[:-1]
        interfaces_vlan.append(line + [vlans_compact_str])
    return vlan_info, interfaces_vlan
