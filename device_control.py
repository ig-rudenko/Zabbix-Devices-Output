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

    # -------------------------------------ELTEX-ESR
    if vendor.lower() == 'eltex-esr':
        intf_list = findall(rf"(\S+\d)\s+\S+\s+\S+\s+(\S*{interface_filter}\S*)", output)
        mac_output = ''
        for intf in intf_list:
            telnet_session.sendline(f'show mac address-table interface {interface_normal_view(intf[0])}')
            telnet_session.expect('# ')
            m_output = sub('.+\nVID', 'VID', str(telnet_session.before.decode('utf-8')))
            mac_output += f"\n    Интерфейс: {intf[1]}\n\n{m_output}"
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
            if (not not_uplinks and bool(findall(interface_filter, line[2]))) or \
                    (not_uplinks and 'SVSL' not in line[2] and line[2]):
                intf_to_check.append([line[0], line[2]])

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
            if (not not_uplinks and bool(findall(interface_filter, line[3]))) or \
                    (not_uplinks and 'SVSL' not in line[3] and line[3]):
                intf_to_check.append(line[0])
        for intf in intf_to_check:
            telnet_session.sendline(f'show fdb port {interface_normal_view(intf)}')
            telnet_session.expect('#')
            mc_output = sub(r'[\W\S]+VID', 'VID', str(telnet_session.before.decode('utf-8')))
            mc_output = sub(r'Total Entries[\s\S]+', ' ', mc_output)

            mac_output += f"\n    Интерфейс: {intf}\n\n{mc_output}"
        if not intf_to_check:
            return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
        return mac_output

    # ----------------------------------------CISCO
    elif vendor == 'cisco':
        with open(f'{root_dir}/templates/int_des_cisco.template', 'r') as template_file:
            int_des_ = textfsm.TextFSM(template_file)
            result = int_des_.ParseText(output)  # Ищем интерфейсы

        intf_to_check = []  # Интерфейсы для проверки
        mac_output = ''     # Вывод MAC
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in result:
            if (not not_uplinks and bool(findall(interface_filter, line[2]))) or (
                    not_uplinks and 'SVSL' not in line[2] and line[2]):     # Если описание интерфейсов удовлетворяет фильтру
                intf_to_check.append([line[0], line[2]])

        for intf in intf_to_check:  # для каждого интерфейса
            telnet_session.sendline(f'show mac address-table interface {interface_normal_view(intf[0])}')
            mac_output += f'\n    Интерфейс: {interface_normal_view(intf[1])}\n'
            while True:
                match = telnet_session.expect([r'#$', "--More--", pexpect.TIMEOUT])
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
            mac_output += '\n'
        return mac_output

    # ------------------------------------HUAWEI_FIRST_TYPE
    elif vendor == 'huawei-1':
        intf_to_check = []  # Интерфейсы для проверки
        mac_output = ''  # Вывод MAC
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in output:
            if (not not_uplinks and bool(findall(interface_filter, line[3]))) or (
                    not_uplinks and 'SVSL' not in line[3] and line[3]):  # Если описание интерфейсов удовлетворяет фильтру
                intf_to_check.append([line[0], line[3]])

        for intf in intf_to_check:  # для каждого интерфейса
            telnet_session.sendline(f'display mac-address {interface_normal_view(intf[0])}')
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
        not_uplinks = True if interface_filter == '--only-abonents' else False

        for line in output:
            if (not not_uplinks and bool(findall(interface_filter, line[2]))) or (
                    not_uplinks and 'SVSL' not in line[2] and line[2]):  # Если описание интерфейсов удовлетворяет фильтру
                intf_to_check.append([line[0], line[2]])

        for intf in intf_to_check:  # для каждого интерфейса
            telnet_session.sendline(f'display mac-address interface {interface_normal_view(intf[0])}')
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


def show_interfaces(dev: str, ip: str, mode: str = '', interface_filter: str = 'NOMON'):
    # Список авторизации
    auth_list = [
        ['NOC', 'oncenoc2020!@#'],
        ['boxroot', 'eghfdktybt']
    ]

    with pexpect.spawn(f"telnet {ip}") as telnet:
        try:
            for user, password in auth_list:
                login_stat = telnet.expect(["[Ll]ogin", "[Uu]ser", "[Nn]ame", 'Unable to connect'], timeout=20)
                if login_stat == 3:
                    print("    Telnet недоступен!")
                    return False
                telnet.sendline(user)
                telnet.expect("[Pp]ass")
                telnet.sendline(password)
                match = telnet.expect([']', '>', '#', 'Failed to send authen-req', "[Ll]ogin", "[Uu]ser\s", "[Nn]ame"])
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
            # ZTE
            if bool(findall(r' ZTE Corporation:', version)):
                print("    Тип оборудования: ZTE\nНе поддерживается в данной версии")

            # ---------------------------------Huawei
            elif bool(findall(r'Unrecognized command', version)):
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
                            vendor=huawei_type,
                            interface_filter=interface_filter
                        )
                    )

            # ---------------------------------Cisco
            elif bool(findall(r'Cisco IOS', version)):
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
                             headers=['\nInterface', 'Admin\nStatus', '\nLink', '\nDescription']
                             )
                )

                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=output,
                            vendor='cisco',
                            interface_filter=interface_filter
                        )
                    )

            # -----------------------------D-Link
            elif bool(findall(r'Next possible completions:', version)):
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
            elif bool(findall(r'SW version\s+', version)):
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

            # ----------------------------Edge-Core
            elif bool(findall(r'Hardware version', version)):
                print("    Тип оборудования: Edge-Core")
                telnet.sendline('show running-config')
                output = ''
                while True:
                    match = telnet.expect(['---More---', '#', pexpect.TIMEOUT])
                    page = str(telnet.before.decode('utf-8'))
                    output += page.strip()
                    if match == 0:
                        telnet.sendline(' ')
                    elif match == 1:
                        break
                    else:
                        print("    Ошибка: timeout")
                        break
                result = []
                intf_raw = findall(r'(interface (.+\n)+?!)', str(output))
                for x in intf_raw:
                    result.append([findall(r'interface (\S*\s*\S*\d)', str(x))[0],
                                   'admin down' if 'shutdown' in str(x) else 'up',
                                   findall(r'description (\S+)', str(x))[0] if len(
                                       findall(r'description (\S+)', str(x))) > 0 else ''])
                print(
                    tabulate(result,
                             headers=['\nInterface', 'Admin\nStatus', '\nDescription'],
                             tablefmt="fancy_grid"
                             )
                )

            # Zyxel
            elif bool(findall(r'ZyNOS', version)):
                print("    Тип оборудования: Zyxel\nНе поддерживается в данной версии")

            # ------------------------------------Eltex
            elif bool(findall(r'Active-image: |Boot version:', version)):
                print("    Eltex")
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
