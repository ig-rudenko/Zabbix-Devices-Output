#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import pexpect
from re import findall
import os
import sys
import textfsm
from tabulate import tabulate
from vendors import cisco, huawei, zte, d_link, alcatel_linksys, eltex, edge_core, extreme, qtech
from auth_list import auth_list

root_dir = os.path.join(os.getcwd(), os.path.split(sys.argv[0])[0])


def show_mac(telnet_session, output, vendor: str, interface_filter: str) -> str:

    # EXTREME
    if vendor == 'extreme':
        return extreme.show_mac(telnet_session, output, interface_filter)

    # ZTE
    elif vendor.lower() == 'zte':
        return zte.show_mac(telnet_session, output, interface_filter)

    # ELTEX-ESR
    elif vendor.lower() == 'eltex-esr':
        return eltex.show_mac_esr_12vf(telnet_session)

    # ELTEX-MES
    elif vendor.lower() == 'eltex-mes':
        return eltex.show_mac_mes(telnet_session, output, interface_filter)

    # D-LINK
    elif vendor == 'd-link':
        return d_link.show_mac(telnet_session, output, interface_filter)

    # CISCO
    elif vendor == 'cisco':
        return cisco.show_mac(telnet_session, output, interface_filter)

    # HUAWEI_FIRST_TYPE
    elif vendor == 'huawei-1':
        return huawei.show_mac_huawei_1(telnet_session, output, interface_filter)

    # HUAWEI_SECOND_TYPE
    elif vendor == 'huawei-2':
        return huawei.show_mac_huawei_2(telnet_session, output, interface_filter)

    # Q-TECH
    elif vendor == 'q-tech':
        return qtech.show_mac(telnet_session, output, interface_filter)


def show_information(dev: str, ip: str, mode: str = '', interface_filter: str = 'NOMON'):

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
                match = telnet.expect([r']$', r'>$', '#', 'Failed to send authen-req', "[Ll]ogin(?!-)", "[Uu]ser\s", "[Nn]ame", 'Fail!'])
                if match < 3:
                    break
            else:   # Если не удалось зайти под логинами и паролями из списка аутентификации
                print('    Неверный логин или пароль!')
                return False
            print(f"    Подключаемся к {dev} ({ip})\n")
            telnet.sendline('show version')
            version = ''
            while True:
                m = telnet.expect([r']$', '-More-', r'>$', r'#', pexpect.TIMEOUT])
                version += str(telnet.before.decode('utf-8'))
                if m == 1:
                    telnet.sendline(' ')
                if m == 4:
                    telnet.sendcontrol('C')
                else:
                    break
            # ZTE
            if findall(r' ZTE Corporation:', version):
                print("    Тип оборудования: ZTE")
                if 'показать_интерфейсы' in mode:
                    result = zte.show_interfaces(telnet)

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

            # Huawei
            elif findall(r'Unrecognized command', version):
                print("    Тип оборудования: Huawei")
                if 'показать_интерфейсы' in mode:
                    result, huawei_type = huawei.show_interfaces(telnet_session=telnet)

                    if huawei_type == 'huawei-1':
                        print(
                            tabulate(result,
                                     headers=['\nInterface', 'Port\nStatus', '\nDescription'],
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
                if 'sys-info' in mode:
                    print(huawei.show_device_info(telnet_session=telnet))

            # Cisco
            elif findall(r'Cisco IOS', version):
                print("    Тип оборудования: Cisco")
                if 'показать_интерфейсы' in mode:
                    if match == 1:  # если поймали `>`
                        telnet.sendline('enable')
                        telnet.expect('[Pp]ass')
                        telnet.sendline('sevaccess')
                    telnet.expect('#')
                    result = cisco.show_interfaces(telnet_session=telnet)

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
                if 'sys-info' in mode:
                    print(cisco.show_device_info(telnet_session=telnet))

            # D-Link
            elif findall(r'Next possible completions:', version):
                print("    Тип оборудования: D-Link")
                if 'показать_интерфейсы' in mode:
                    result = d_link.show_interfaces(telnet_session=telnet)
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
                if 'sys-info' in mode:
                    print(d_link.show_device_info(telnet_session=telnet))

            # Alcatel, Linksys
            elif findall(r'SW version\s+', version):
                print("    Тип оборудования: Alcatel или Linksys")
                if 'показать_интерфейсы' in mode:
                    result = alcatel_linksys.show_interfaces(telnet_session=telnet)
                    print(
                        tabulate(result,
                                 headers=['\nInterface', 'Admin\nStatus',  '\nLink', '\nDescription'],
                                 tablefmt="fancy_grid"
                                 )
                    )
                if 'mac' in mode:
                    print("Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉")

            # Edge-Core
            elif findall(r'Hardware version', version):
                print("    Тип оборудования: Edge-Core")
                if 'показать_интерфейсы' in mode:
                    result = edge_core.show_interfaces(telnet_session=telnet)
                    print(
                        tabulate(result,
                                 headers=['\nInterface', 'Admin\nStatus',  '\nLink', '\nDescription'],
                                 tablefmt="fancy_grid"
                                 )
                    )
                if 'mac' in mode:
                    print("Для данного типа оборудования просмотр MAC'ов в данный момент недоступен 🦉")

            # Zyxel
            elif findall(r'ZyNOS', version):
                print("    Тип оборудования: Zyxel\nНе поддерживается в данной версии!🐣")

            # Eltex
            elif findall(r'Active-image: |Boot version:', version):
                print("    Тип оборудования: Eltex")
                if 'показать_интерфейсы' in mode:
                    output = eltex.show_interfaces(telnet_session=telnet)
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
                if 'sys-info' in mode:
                    print(eltex.show_device_info(telnet_session=telnet))

            # Extreme
            elif findall(r'ExtremeXOS', version):
                print("    Тип оборудования: Extreme")
                if 'показать_интерфейсы' in mode:
                    result = extreme.show_interfaces(telnet_session=telnet)

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
                            vendor='extreme',
                            interface_filter=interface_filter
                        )
                    )

            # Q-TECH
            elif findall(r'QTECH', version):
                print("    Тип оборудования: Q-Tech")
                if 'показать_интерфейсы' in mode:
                    result = qtech.show_interfaces(telnet_session=telnet)
                    print(
                        tabulate(result,
                                 headers=['\nInterface', 'Link\nStatus', '\nDescription'],
                                 tablefmt="fancy_grid"
                                 )
                    )
                if 'mac' in mode:
                    print(
                        show_mac(
                            telnet_session=telnet,
                            output=result,
                            vendor='q-tech',
                            interface_filter=interface_filter
                        )
                    )

        except pexpect.exceptions.TIMEOUT:
            print("    Время ожидания превышено! (timeout)")

# device_name = sys.argv[1]   # 'SVSL-933-Odesskaya5-SZO'
# ip = sys.argv[2]            # eltex '192.168.195.19' d-link '172.20.69.106' cisco '192.168.228.57'
# mode = sys.argv[3]          # '--show-interfaces'


interface_filter = ''

if len(sys.argv) < 4:
    print('Не достаточно аргументов, операция прервана!')
    sys.exit()

device_name = sys.argv[1]
ip = sys.argv[2]
mode = sys.argv[3]

if len(sys.argv) >= 5:
    interface_filter = sys.argv[4]

show_information(dev=device_name,
                 ip=ip,
                 mode=mode,
                 interface_filter=interface_filter
                 )
