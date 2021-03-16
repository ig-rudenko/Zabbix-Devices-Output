import pexpect
from re import findall, sub
import sys
from core import textfsm
from core.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_mac(telnet_session, interfaces: list, interface_filter: str) -> str:

    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    not_uplinks = True if interface_filter == 'only-abonents' else False

    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[2].upper() and  # - интерфейсов, которые содержат "SVSL"
                    'POWER_MONITORING' not in line[2].upper())  # - POWER_MONITORING
                and not ('down' in line[1].lower() and not line[2])  # - пустые интерфейсы с LinkDown
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
    telnet_session.sendline("show interface ethernet status")
    output = ''
    while True:
        match = telnet_session.expect([r'[#>]$', "--More--", pexpect.TIMEOUT])
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
    output = sub('[\W\S]+\nInterface', '\nInterface', output)
    with open(f'{root_dir}/templates/int_des_q-tech.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return result


def show_device_info(telnet_session):
    info = ''
    # VERSION
    telnet_session.sendline('show version')
    telnet_session.expect('show version')
    telnet_session.expect('\S+#')
    info += str(telnet_session.before.decode('utf-8'))

    # TEMPERATURE
    telnet_session.sendline('show temperature')
    telnet_session.expect('show temperature')
    telnet_session.expect('\S+#')
    info += '   ┌─────────────┐\n'
    info += '   │ Температура │\n'
    info += '   └─────────────┘\n'
    info += str(telnet_session.before.decode('utf-8'))

    # FANS
    telnet_session.sendline('show fan')
    telnet_session.expect('show fan')
    telnet_session.expect('\S+#')
    info += '   ┌──────┐\n'
    info += '   │ FANS │\n'
    info += '   └──────┘\n'
    info += str(telnet_session.before.decode('utf-8'))

    # SNMP
    telnet_session.sendline('show snmp status')
    telnet_session.expect('show snmp status')
    telnet_session.expect('\S+#')
    info += '   ┌──────┐\n'
    info += '   │ SNMP │\n'
    info += '   └──────┘\n'
    info += str(telnet_session.before.decode('utf-8'))
    return info
