#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pexpect
from re import findall, sub
import os
import sys
import textfsm
from tabulate import tabulate

root_dir = os.path.join(os.getcwd(), os.path.split(sys.argv[0])[0])


def interface_normal_view(interface) -> str:
    """
    Приводит имя интерфейса к виду принятому по умолчанию для коммутаторов\n
    Например: Eth 0/1 -> Ethernet0/1
              GE1/0/12 -> GigabitEthernet1/0/12\n
    :param interface:   Интерфейс в сыром виде (raw)
    :return:            Интерфейс в общепринятом виде
    """
    interface = str(interface)
    interface_number = findall(r'(\d+([/\\]?\d*)*)', str(interface))
    if bool(findall('^[Ee]t', interface)):
        return f"Ethernet {interface_number[0][0]}"
    elif bool(findall('^[Ff]a', interface)):
        return f"FastEthernet {interface_number[0][0]}"
    elif bool(findall('^[Gg]i', interface)):
        return f"GigabitEthernet {interface_number[0][0]}"
    elif bool(findall('^\d+', interface)):
        return findall('^\d+', interface)[0]
    elif bool(findall('^[Tt]e', interface)):
        return f'TengigabitEthernet {interface_number[0][0]}'
    else:
        return interface


def show_mac(telnet_session, output: str, vendor: str, interface_filter: str) -> str:

    # ----------------------------------------ZTE
    if vendor.lower() == 'zte':
        intf_to_check = []
        mac_output = ''
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in output:
            if (
                    (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                    or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                        'SVSL' not in line[3].upper() and  # - интерфейсов, которые содержат "SVSL"
                        'POWER_MONITORING' not in line[3].upper())  # - POWER_MONITORING
                    and not ('down' in line[2].lower() and not line[3])  # - пустые интерфейсы с LinkDown
                    and 'disabled' not in line[1].lower()  # И только интерфейсы со статусом admin up
            ):  # Если описание интерфейсов удовлетворяет фильтру
                intf_to_check.append([line[0], line[3]])

        if not intf_to_check:
            if not_uplinks:
                return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
            else:
                return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                       f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

        for intf in intf_to_check:
            telnet_session.sendline(f'show fdb port {interface_normal_view(intf[0])} detail')
            telnet_session.expect('detail')
            mc_output = ''
            while True:
                match = telnet_session.expect([r'#$', "----- more -----", pexpect.TIMEOUT])
                page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                    "        ", '')
                mc_output += page.strip()
                if match == 0:
                    break
                elif match == 1:
                    telnet_session.send(" ")
                    mc_output += '\n'
                else:
                    print("    Ошибка: timeout")
                    break
            mc_output = sub(r'Fixed:\s*\d+([\W\S]+)', ' ', mc_output)
            mc_output = sub(r'MacAddressVlan', '  Mac Address       Vlan', mc_output)
            mc_output = sub(r'%\s+No matching mac address![\W\S]+', '  No matching mac address!', mc_output)
            separator_str = '─'*len(f'Интерфейс: {intf[0]} ({intf[1]})')
            mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n{mc_output}\n\n"
        if not intf_to_check:
            return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
        return mac_output

    # -------------------------------------ELTEX-ESR
    elif vendor.lower() == 'eltex-esr':
        # Для Eltex ESR-12VF выводим всю таблицу MAC адресов
        mac_output = ''
        telnet_session.sendline(f'show mac address-table ')
        telnet_session.expect('# ')
        m_output = sub('.+\nVID', 'VID', str(telnet_session.before.decode('utf-8')))
        mac_output += f"\n{m_output}"
        return mac_output

    # -------------------------------------ELTEX-MES

    elif vendor.lower() == 'eltex-mes':
        intf_to_check = []  # Интерфейсы для проверки
        mac_output = ''     # Вывод MAC
        not_uplinks = True if interface_filter == '--only-abonents' else False

        with open(f'{root_dir}/templates/int_des_eltex.template', 'r') as template_file:
            int_des_ = textfsm.TextFSM(template_file)
            result = int_des_.ParseText(output)  # Ищем интерфейсы

        for line in result:
            if (
                    (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                    or (not_uplinks and                                 # ИЛИ все интерфейсы, кроме:
                        'SVSL' not in line[3].upper() and                    # - интерфейсов, которые содержат "SVSL"
                        'POWER_MONITORING' not in line[3].upper())           # - POWER_MONITORING
                        and not ('down' in line[2].lower() and not line[3])  # - пустые интерфейсы с LinkDown
                    and 'down' not in line[1].lower()                   # И только интерфейсы со статусом admin up
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
            mac_output += f'\n    Интерфейс: {intf[1]}\n'
            telnet_session.expect('Aging time')
            mac_output += 'Aging time '
            while True:
                match = telnet_session.expect([r'#$', "More: <space>", pexpect.TIMEOUT])
                page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                    "        ", '')
                mac_output += page.strip()
                if match == 0:
                    break
                elif match == 1:
                    telnet_session.send(" ")
                else:
                    print("    Ошибка: timeout")
                    break
            mac_output += '\n'
        return mac_output

    # ---------------------------------------D-LINK
    elif vendor == 'd-link':
        intf_to_check = []
        mac_output = ''
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in output:
            if (
                    (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                    or (not_uplinks and                                     # ИЛИ все интерфейсы, кроме:
                        'SVSL' not in line[3].upper() and                       # - интерфейсов, которые содержат "SVSL"
                        'POWER_MONITORING' not in line[3].upper())              # - POWER_MONITORING
                        and not ('down' in line[2].lower() and not line[3])     # - пустые интерфейсы с LinkDown
                    and 'disabled' not in line[1].lower()                   # И только интерфейсы со статусом admin up
            ):  # Если описание интерфейсов удовлетворяет фильтру
                intf_to_check.append([line[0], line[3]])

        if not intf_to_check:
            if not_uplinks:
                return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
            else:
                return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                       f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

        for intf in intf_to_check:
            telnet_session.sendline(f'show fdb port {interface_normal_view(intf[0])}')
            telnet_session.expect('#')
            mc_output = sub(r'[\W\S]+VID', 'VID', str(telnet_session.before.decode('utf-8')))
            mc_output = sub(r'Total Entries[\s\S]+', ' ', mc_output)
            separator_str = '─'*len(f'Интерфейс: {intf[0]} ({intf[1]})')
            mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n{mc_output}"
        if not intf_to_check:
            return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
        return mac_output

    # ----------------------------------------CISCO
    elif vendor == 'cisco':

        intf_to_check = []  # Интерфейсы для проверки
        mac_output = ''     # Вывод MAC
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in output:
            if (
                    (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                    or (not_uplinks and                                     # ИЛИ все интерфейсы, кроме:
                        'SVSL' not in line[3].upper() and                       # - интерфейсов, которые содержат "SVSL"
                        'POWER_MONITORING' not in line[3].upper())              # - POWER_MONITORING
                        and not ('down' in line[2].lower() and not line[3])     # - пустые интерфейсы с LinkDown
                    and 'down' not in line[1].lower()                       # И только интерфейсы со статусом admin up
                    and 'VL' not in line[0].upper()                         # И не VLAN'ы
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

    # ------------------------------------HUAWEI_FIRST_TYPE
    elif vendor == 'huawei-1':
        intf_to_check = []  # Интерфейсы для проверки
        mac_output = ''  # Вывод MAC
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in output:
            if (
                    (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                    or (not_uplinks and                          # ИЛИ все интерфейсы, кроме:
                        'SVSL' not in line[3].upper() and             # - интерфейсов, которые содержат "SVSL"
                        'HUAWEI, QUIDWAY' not in line[3].upper() and  # - "заглушек" типа "HUAWEI, Quidway Series
                        'POWER_MONITORING' not in line[3].upper())    # - POWER_MONITORING
                    and 'down' not in line[1].lower()            # И только интерфейсы со статусом admin up
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

    # ------------------------------------HUAWEI_SECOND_TYPE
    elif vendor == 'huawei-2':

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


def show_interfaces(dev: str, ip: str, mode: str = '', interface_filter: str = 'NOMON'):
    # Список авторизации
    auth_list = [
        ['NOC', 'oncenoc2020!@#'],
        ['boxroot', 'eghfdktybt']
    ]

    with pexpect.spawn(f"telnet {ip}") as telnet:
        try:
            for user, password in auth_list:
                login_stat = telnet.expect(["[Ll]ogin", "[Uu]ser", "[Nn]ame", 'Unable to connect', 'Connection closed'],
                                           timeout=20)
                if login_stat >= 3:
                    print("    Telnet недоступен!")
                    return False
                telnet.sendline(user)
                telnet.expect("[Pp]ass")
                telnet.sendline(password)
                match = telnet.expect([r']$', r'>$', '#', 'Failed to send authen-req', "[Ll]ogin(?!-)", "[Uu]ser\s", "[Nn]ame"])
                if match < 3:
                    break
            else:   # Если не удалось зайти под логинами и паролями из списка аутентификации
                print('    Неверный логин или пароль!')
                return False
            print(f"    Подключаемся к {dev} ({ip})\n")
            telnet.sendline('show version')
            version = ''
            while True:
                m = telnet.expect([r']$', '-More-', r'>$', r'#'])
                version += str(telnet.before.decode('utf-8'))
                if m == 1:
                    telnet.sendline(' ')
                else:
                    break
            # ---------------------------------ZTE
            if findall(r' ZTE Corporation:', version):
                print("    Тип оборудования: ZTE")
                telnet.sendline('enable')
                telnet.expect('[Pp]ass')
                telnet.sendline('sevaccess')
                telnet.expect('#')
                telnet.sendline('show port')
                output = ''
                while True:
                    match = telnet.expect([r'#$', "----- more -----", pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace("[42D", '').replace(
                        "        ", '')
                    output += page.strip()
                    if match == 0:
                        break
                    elif match == 1:
                        telnet.send(" ")
                        output += '\n'
                    else:
                        print("    Ошибка: timeout")
                        break
                with open(f'{root_dir}/templates/int_des_zte.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result = int_des_.ParseText(output)  # Ищем интерфейсы

                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus', '\nLink', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )

                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=result,
                            vendor='zte',
                            interface_filter=interface_filter
                        )
                    )

            # ---------------------------------Huawei
            elif findall(r'Unrecognized command', version):
                print("    Тип оборудования: Huawei")
                telnet.sendline("dis int des")
                output = ''
                huawei_type = 'huawei-1'
                template_type = ''
                while True:
                    match = telnet.expect(['Too many parameters', ']', "  ---- More ----",
                                           "Unrecognized command", ">", pexpect.TIMEOUT])
                    output += str(telnet.before.decode('utf-8')).replace(
                        "\x1b[42D                                          \x1b[42D", '').replace("[42D", '').strip()
                    if match == 4:
                        break
                    elif match == 1:
                        break
                    elif match == 2:
                        telnet.send(" ")
                        output += '\n\n'
                    elif match == 0 or match == 3:
                        telnet.expect('>')
                        telnet.sendline('super')
                        telnet.expect(':')
                        telnet.sendline('sevaccess')
                        telnet.expect('>')
                        telnet.sendline('dis brief int')
                        output = ''
                        huawei_type = 'huawei-2'
                        template_type = '2'
                    else:
                        print("    Ошибка: timeout")
                        break

                with open(f'{root_dir}/templates/int_des_huawei{template_type}.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result = int_des_.ParseText(output)  # Ищем интерфейсы

                if huawei_type == 'huawei-1':
                    print(
                        tabulate(result,
                                 headers=['\nInterface', 'Admin\nStatus', '\nLink', '\nDescription'],
                                 tablefmt="fancy_grid"
                                 )
                    )
                else:
                    print(
                        tabulate(result,
                                 headers=['\nInterface', 'Port\nStatus', '\nDescription'],
                                 tablefmt="fancy_grid"
                                 )
                    )

                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=result,
                            vendor=huawei_type,
                            interface_filter=interface_filter
                        )
                    )

            # ---------------------------------Cisco
            elif findall(r'Cisco IOS', version):
                print("    Тип оборудования: Cisco")
                if match == 1:
                    telnet.sendline('enable')
                    telnet.expect('[Pp]ass')
                    telnet.sendline('sevaccess')
                telnet.expect('#')
                telnet.sendline("show int des")
                output = ''
                while True:
                    match = telnet.expect([r'#$', "--More--", pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace("[42D", '').replace(
                        "        ", '')
                    output += page.strip()
                    if match == 0:
                        break
                    elif match == 1:
                        telnet.send(" ")
                        output += '\n'
                    else:
                        print("    Ошибка: timeout")
                        break
                output = sub('.+\nInterface', 'Interface', output)
                with open(f'{root_dir}/templates/int_des_cisco.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result = int_des_.ParseText(output)  # Ищем интерфейсы

                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus', '\nLink', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )

                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=result,
                            vendor='cisco',
                            interface_filter=interface_filter
                        )
                    )

            # -----------------------------D-Link
            elif findall(r'Next possible completions:', version):
                print("    Тип оборудования: D-Link")
                telnet.sendline('enable admin')
                if telnet.expect(["#", "[Pp]ass"]):
                    telnet.sendline('sevaccess')
                    telnet.expect('#')
                telnet.sendline('disable clipaging')
                telnet.expect('#')
                telnet.sendline("show ports des")
                telnet.expect('#')
                output = telnet.before.decode('utf-8')
                with open(f'{root_dir}/templates/int_des_d-link.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result = int_des_.ParseText(output)  # Ищем интерфейсы
                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus', '\nConnection', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )

                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=result,
                            vendor='d-link',
                            interface_filter=interface_filter
                        )
                    )

            # ---------------------------Alcatel, Linksys
            elif findall(r'SW version\s+', version):
                print("    Тип оборудования: Alcatel или Linksys")
                telnet.sendline('show interfaces configuration')
                port_state = ''
                while True:
                    match = telnet.expect(['More: <space>', '#', pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8'))
                    port_state += page.strip()
                    if match == 0:
                        telnet.sendline(' ')
                    elif match == 1:
                        break
                    else:
                        print("    Ошибка: timeout")
                        break

                # Description
                with open(f'{root_dir}/templates/int_des_alcatel_linksys.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result_port_state = int_des_.ParseText(port_state)  # Ищем интерфейсы
                telnet.sendline('show int des')
                telnet.expect('#')
                port_desc = ''
                while True:
                    match = telnet.expect(['More: <space>', '#', pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8'))
                    port_desc += page.strip()
                    if match == 0:
                        telnet.sendline(' ')
                    elif match == 1:
                        break
                    else:
                        print("    Ошибка: timeout")
                        break
                with open(f'{root_dir}/templates/int_des_alcatel_linksys2.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result_port_des = int_des_.ParseText(port_desc)  # Ищем интерфейсы

                # Ищем состояние порта
                telnet.sendline('show int status')
                telnet.expect('#')
                port_desc = ''
                while True:
                    match = telnet.expect(['More: <space>', '#', pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8'))
                    port_desc += page.strip()
                    if match == 0:
                        telnet.sendline(' ')
                    elif match == 1:
                        telnet.sendline('exit')
                        break
                    else:
                        print("    Ошибка: timeout")
                        break
                with open(f'{root_dir}/templates/int_des_alcatel_linksys_link.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result_port_link = int_des_.ParseText(port_desc)  # Ищем интерфейсы

                result = []
                for postition, line in enumerate(result_port_state):
                    result.append([line[0],                         # interface
                                   line[1],                         # admin status
                                   result_port_link[postition][0],  # link
                                   result_port_des[postition][0]])  # description
                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus',  '\nLink', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )

                if 'mac' in mode:
                    print("Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉" )

            # ----------------------------Edge-Core
            elif findall(r'Hardware version', version):
                print("    Тип оборудования: Edge-Core")
                telnet.sendline('show running-config')
                output = ''
                while True:
                    match = telnet.expect(['---More---', '#', pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace(
                        '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08',
                        '')
                    output += page.strip()
                    if match == 0:
                        telnet.sendline(' ')
                    elif match == 1:
                        break
                    else:
                        print("    Ошибка: timeout")
                        break

                telnet.sendline('show interfaces status')
                telnet.expect('show interfaces status')
                des_output = ''
                while True:
                    match = telnet.expect(['---More---', '#', pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace(
                        '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08',
                        '')
                    des_output += page.strip()
                    if match == 0:
                        telnet.sendline(' ')
                    elif match == 1:
                        break
                    else:
                        print("    Ошибка: timeout")
                        break
                with open(f'{root_dir}/templates/int_des_edge_core.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result_des = int_des_.ParseText(des_output)  # Ищем интерфейсы
                for i in result_des:
                    print(i)

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
                    result.append([interface,
                                   admin_status,
                                   link_stat,
                                   description])
                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus',  '\nLink', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )

                if 'mac' in mode:
                    print("Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉" )

            # Zyxel
            elif findall(r'ZyNOS', version):
                print("    Тип оборудования: Zyxel\nНе поддерживается в данной версии!🐣")

            # ------------------------------------Eltex
            elif findall(r'Active-image: |Boot version:', version):
                print("    Тип оборудования: Eltex")
                telnet.sendline("show int des")
                output = ''
                while True:
                    match = telnet.expect([r'# ', "More: <space>", pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace("[42D", '').replace(
                        "        ", '')
                    output += page.strip()
                    if 'Ch       Port Mode (VLAN)' in output:
                        telnet.sendline('q')
                        telnet.expect('#')
                        break
                    if match == 0:
                        break
                    elif match == 1:
                        telnet.send(" ")
                    else:
                        print("    Ошибка: timeout")
                        break
                output = sub('.+\nInterface', 'Interface', output)
                output = sub('\s+Admin Link\s+Ch       Port Mode \(VLAN\)[\s\S]+', '', output)

                if bool(findall(r'Active-image:', version)):
                    eltex_type = 'eltex-mes'
                    with open(f'{root_dir}/templates/int_des_eltex.template', 'r') as template_file:
                        int_des_ = textfsm.TextFSM(template_file)
                        result = int_des_.ParseText(output)  # Ищем интерфейсы
                    print(
                        tabulate(result,
                                 headers=['\nInterface', 'Admin\nStatus', '\nLink', '\nDescription'],
                                 tablefmt="fancy_grid"
                                 )
                    )

                elif bool(findall(r'Boot version:', version)):
                    eltex_type = 'eltex-esr'
                    print(output)

                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=output,
                            vendor=eltex_type,
                            interface_filter=interface_filter
                        )
                    )

            # -----------------------------------Extreme
            elif findall(r'ExtremeXOS', version):
                print("    Тип оборудования: Extreme")

                # LINKS
                telnet.sendline('show ports information')
                output_links = ''
                while True:
                    match = telnet.expect([r'# ', "Press <SPACE> to continue or <Q> to quit:", pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace("[42D", '').replace(
                        "\x1b[m\x1b[60;D\x1b[K", '')
                    output_links += page.strip()
                    if match == 0:
                        break
                    elif match == 1:
                        telnet.send(" ")
                        output_links += '\n'
                    else:
                        print("    Ошибка: timeout")
                        break
                with open(f'{root_dir}/templates/int_des_extreme_links.template', 'r') as template_file:
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
                telnet.sendline('show ports description')
                output_des = ''
                while True:
                    match = telnet.expect([r'# ', "Press <SPACE> to continue or <Q> to quit:", pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8')).replace("[42D", '').replace(
                        "\x1b[m\x1b[60;D\x1b[K", '')
                    output_des += page.strip()
                    if match == 0:
                        break
                    elif match == 1:
                        telnet.send(" ")
                        output_des += '\n'
                    else:
                        print("    Ошибка: timeout")
                        break
                with open(f'{root_dir}/templates/int_des_extreme_des.template', 'r') as template_file:
                    int_des_ = textfsm.TextFSM(template_file)
                    result_des = int_des_.ParseText(output_des)  # Ищем desc

                result = [result_port_state[n] + result_des[n] for n in range(len(result_port_state))]

                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus', '\nLink', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )
                if 'mac' in mode:
                    print("Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉" )

            # Q-TECH
            elif findall(r'QTECH', version):
                print("    Тип оборудования: Q-Tech\nНе поддерживается в данной версии!🐣")
        except pexpect.exceptions.TIMEOUT:
            print("    Время ожидания превышено! (timeout)")

# device_name = sys.argv[1]   # 'SVSL-933-Odesskaya5-SZO'
# ip = sys.argv[2]            # eltex '192.168.195.19' d-link '172.20.69.106' cisco '192.168.228.57'
# mode = sys.argv[3]          # '--show-interfaces'


mode = ''
interface_filter = ''

if len(sys.argv) < 3:
    print('Не достаточно аргументов, операция прервана!')
    sys.exit()

device_name = sys.argv[1]
ip = sys.argv[2]

if len(sys.argv) >= 5:
    mode = sys.argv[3]
    interface_filter = sys.argv[4]

show_interfaces(dev=device_name,
                ip=ip,
                mode=mode,
                interface_filter=interface_filter
                )
