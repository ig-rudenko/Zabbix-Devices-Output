import pexpect
from re import findall, sub
import sys
import textfsm
from core.misc import interface_normal_view
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, prompt: str = r'\S+#$', next_catch: str = None):
    return sendcmd(session, command, prompt=prompt, space_prompt="--More--", before_catch=next_catch)


def show_mac(session, interfaces: list, interface_filter: str) -> str:
    mac_output = ''

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for intf in intf_to_check:  # для каждого интерфейса
        session.sendline(f'show mac address-table interface {interface_normal_view(intf[0])}')
        session.expect(f'-------------------')
        session.expect('Vla')
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(intf[1])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n' \
                      f'    {separator_str}\n' \
                      f'Vla'
        while True:
            match = session.expect(
                [
                    'Total Mac Addresses',  # 0 - найдены все MAC адреса
                    r'#$',                  # 1 - конец
                    "--More--",             # 2 - Далее
                    pexpect.TIMEOUT         # 3
                ]
            )
            page = str(session.before.decode('utf-8')).replace("[42D", '').replace(
                "        ", '')
            mac_output += page.strip()
            if match <= 1:
                break
            elif match == 2:
                session.send(" ")
                mac_output += '\n'
            else:
                print("    Ошибка: timeout")
                break
        mac_output += '\n\n'
    return mac_output


def show_interfaces(session) -> list:
    output = send_command(
        session=session,
        command='show int des'
    )
    output = sub('.+\nInterface', 'Interface', output)
    with open(f'{sys.path[0]}/templates/interfaces/cisco.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы

    return [line for line in result if not line[0].startswith('V')]


def get_device_info(session):
    version = send_command(
        session=session,
        command='show version'
    )
    version = sub(r'\W+This product [\W\S]+cisco\.com\.', '', version)
    version += '\n'

    # ENVIRONMENT
    environment = send_command(
        session=session,
        command='show environment'
    )
    if 'Invalid input' in environment:
        environment = send_command(
            session=session,
            command='show env all'
        )
    environment = f"""
   ┌──────────────────────────────────┐
   │ Температура, Питание, Охлаждение │
   └──────────────────────────────────┘
{environment}
"""
    if 'Invalid input' in environment:
        environment = ''
    version += environment

    # INVENTORY
    inventory = send_command(
            session=session,
            command='show inventory oid'
        )
    if findall(r'Invalid input|% No entity', inventory):
        inventory = send_command(
            session=session,
            command='show inventory'
        )
    inventory = f"""
    ┌────────────────┐
    │ Инвентаризация │
    └────────────────┘
{inventory}
"""
    if findall(r'Invalid input|% No entity', inventory):
        inventory = ''
    version += inventory

    # SNMP
    snmp_info = send_command(
            session=session,
            command='show snmp'
        )
    version += f"""
    ┌──────┐
    │ SNMP │
    └──────┘
{snmp_info}
"""
    # IDPROMs
    extended_tech_info = send_command(
            session=session,
            command='show idprom all'
        )

    extended_tech_info = f"""
    ┌                                    ┐
    │ Расширенная техническая информация │
    └                                    ┘
                      ▼
{extended_tech_info}
    """
    if '% Invalid input' in extended_tech_info:
        extended_tech_info = ''
    version += extended_tech_info

    # mac_address = findall(r'MAC Address\s+:\s+(\S\S:\S\S:\S\S:\S\S:\S\S:\S\S)', version)
    # serial_number = findall(r'System serial number\s+:\s+(\S+)', version)

    return version


def show_vlans(session, interfaces) -> tuple:
    result = []
    for line in interfaces:
        if not line[0].startswith('V'):
            output = send_command(
                session=session,
                command=f"show running-config interface {interface_normal_view(line[0])}",
                next_catch="Building configuration"
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
        command='show vlan brief'
    )
    with open(f'{sys.path[0]}/templates/vlans_templates/cisco_vlan_info.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
