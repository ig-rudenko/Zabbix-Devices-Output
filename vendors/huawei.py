import pexpect
from re import findall, sub
import os
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = os.path.join(os.getcwd(), os.path.split(sys.argv[0])[0])


def show_mac_huawei_1(telnet_session, output: list, interface_filter: str) -> str:
    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    not_uplinks = True if interface_filter == '--only-abonents' else False

    for line in output:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[3].upper() and  # - интерфейсов, которые содержат "SVSL"
                    'HUAWEI, QUIDWAY' not in line[3].upper() and  # - "заглушек" типа "HUAWEI, Quidway Series
                    'POWER_MONITORING' not in line[3].upper())  # - POWER_MONITORING
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
        telnet_session.sendline(f'display mac-address {interface_normal_view(intf[0])}')
        telnet_session.expect(f'{interface_normal_view(intf[0])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n'
        while True:
            match = telnet_session.expect([r'<', "  ---- More ----", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8'))
            mac_output += page.strip()
            if match == 0:
                break
            elif match == 1:
                telnet_session.send(" ")
                mac_output += '\n'
            else:
                print("    Ошибка: timeout")
                break
        mac_output += '\n'
    return mac_output


def show_mac_huawei_2(telnet_session, output: list, interface_filter: str) -> str:
    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC
    # Все интерфейсы, кроме аплинков
    not_uplinks = True if interface_filter == '--only-abonents' else False

    for line in output:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[2])))  # интерфейсы по фильтру
                or (not_uplinks and                          # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[2].upper() and             # - интерфейсов, которые содержат "SVSL"
                    'HUAWEI, QUIDWAY' not in line[2].upper() and  # - "заглушек" типа "HUAWEI, Quidway Series
                    'POWER_MONITORING' not in line[2].upper())    # - POWER_MONITORING
                and 'down' not in line[1].lower()            # И только интерфейсы со статусом admin up
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[2]])

    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

    for intf in intf_to_check:  # для каждого интерфейса
        telnet_session.sendline(f'display mac-address interface {interface_normal_view(intf[0])}')
        telnet_session.expect(f'{interface_normal_view(intf[0])}')
        separator_str = '─' * len(f'Интерфейс: {interface_normal_view(intf[1])}')
        mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n    {separator_str}\n'
        while True:
            match = telnet_session.expect(['  ---  ', "  ---- More ----", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8'))
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


def show_interfaces(telnet_session) -> tuple:
    telnet_session.sendline("dis int des")
    output = ''
    huawei_type = 'huawei-1'
    template_type = ''
    while True:
        match = telnet_session.expect(['Too many parameters', ']', "  ---- More ----",
                               "Unrecognized command", ">", pexpect.TIMEOUT])
        output += str(telnet_session.before.decode('utf-8')).replace(
            "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
        if match == 4:
            break
        elif match == 1:
            break
        elif match == 2:
            telnet_session.send(" ")
            output += '\n\n'
        elif match == 0 or match == 3:
            telnet_session.expect('>')
            telnet_session.sendline('super')
            telnet_session.expect(':')
            telnet_session.sendline('sevaccess')
            telnet_session.expect('>')
            telnet_session.sendline('dis brief int')
            output = ''
            huawei_type = 'huawei-2'
            template_type = '2'
        else:
            print("    Ошибка: timeout")
            break

    with open(f'{root_dir}/templates/int_des_huawei{template_type}.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return result, huawei_type
