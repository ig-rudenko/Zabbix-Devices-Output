import pexpect
from re import findall, sub
import os
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = os.path.join(os.getcwd(), os.path.split(sys.argv[0])[0])


def show_mac(telnet_session, output: list, interface_filter: str) -> str:

    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    not_uplinks = True if interface_filter == '--only-abonents' else False

    for line in output:
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
    return result


def show_device_info(telnet_session):
    version = ''
    # VERSION
    telnet_session.sendline('show version')
    telnet_session.expect('show version')
    while True:
        m = telnet_session.expect([' --More-- ', '\S+#$'])
        version += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '')
        if m == 0:
            telnet_session.sendline(' ')
        else:
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
        version += str(telnet_session.before.decode('utf-8'))
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
        m = telnet_session.expect([' --More-- ', '\S+#$'])
        version += str(telnet_session.before.decode('utf-8'))
        if m == 0:
            telnet_session.sendline(' ')
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
    return version
