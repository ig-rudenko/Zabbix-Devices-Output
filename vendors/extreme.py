import pexpect
from re import findall
import os
import sys
import textfsm

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
                and not ('ready' in line[2].lower() and not line[3])  # - пустые интерфейсы с LinkDown
                and 'disable' not in line[1].lower()  # И только интерфейсы со статусом admin up
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[3]])

    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

    for intf in intf_to_check:  # для каждого интерфейса
        telnet_session.sendline(f'show fdb ports {intf[0]}')
        separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
        mac_output += f'\n    Интерфейс: {intf[0]} ({intf[1]})\n'\
                      f'    {separator_str}\n'
        while True:
            match = telnet_session.expect([r'# ', "Press <SPACE> to continue or <Q> to quit:", pexpect.TIMEOUT])
            page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
                "\x1b[m\x1b[60;D\x1b[K", '')
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
    # LINKS
    telnet_session.sendline('show ports information')
    output_links = ''
    while True:
        match = telnet_session.expect([r'# ', "Press <SPACE> to continue or <Q> to quit:", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "\x1b[m\x1b[60;D\x1b[K", '')
        output_links += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
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
    telnet_session.sendline('show ports description')
    output_des = ''
    while True:
        match = telnet_session.expect([r'# ', "Press <SPACE> to continue or <Q> to quit:", pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "\x1b[m\x1b[60;D\x1b[K", '')
        output_des += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            output_des += '\n'
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/int_des_extreme_des.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_des = int_des_.ParseText(output_des)  # Ищем desc

    result = [result_port_state[n] + result_des[n] for n in range(len(result_port_state))]
    return result


def show_device_info(telnet_session):
    info = '\n'

    # VERSION
    telnet_session.sendline('show switch detail')
    telnet_session.expect('show switch detail\W+')
    while True:
        match = telnet_session.expect([r'\S+\s*#\s*', "Press <SPACE> to continue or <Q> to quit:", pexpect.TIMEOUT])
        info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "\x1b[m\x1b[60;D\x1b[K", '').strip()
        if match == 1:
            telnet_session.send(" ")
            info += '\n'
        else:
            info += '\n'
            break
    telnet_session.sendline('show version detail')
    telnet_session.expect('show version detail\W+')
    telnet_session.expect('\S+\s*#\s*')
    info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "\x1b[m\x1b[60;D\x1b[K", '')

    # FANS
    telnet_session.sendline('show fans detail')
    telnet_session.expect('show fans detail\W+')
    telnet_session.expect('\S+\s*#\s*')
    info += '           ┌────────────┐\n' \
            '           │ Охлаждение │\n' \
            '           └────────────┘\n'
    info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "\x1b[m\x1b[60;D\x1b[K", '')

    # TEMPERATURE
    telnet_session.sendline('show temperature')
    telnet_session.expect('show temperature\W+')
    telnet_session.expect('\S+\s*#\s*')
    info += '           ┌─────────────┐\n' \
            '           │ Температура │\n' \
            '           └─────────────┘\n'
    info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "\x1b[m\x1b[60;D\x1b[K", '')

    # POWER
    telnet_session.sendline('show power')
    telnet_session.expect('show power\W+')
    telnet_session.expect('\S+\s*#\s*')
    info += '           ┌─────────┐\n' \
            '           │ Питание │\n' \
            '           └─────────┘\n'
    info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "\x1b[m\x1b[60;D\x1b[K", '')

    info += ' ┌                                    ┐\n' \
            ' │ Расширенная техническая информация │\n' \
            ' └                                    ┘\n' \
            '                   ▼\n\n' \
            '           ┌───────────────┐\n' \
            '           │ Platform Info │\n' \
            '           └───────────────┘\n'

    # PLATFORM INFORMATION
    telnet_session.sendline('debug hal show platform platformInfo')
    telnet_session.expect('debug hal show platform platformInfo')
    telnet_session.expect('\S+\s*#\s*$')

    info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "\x1b[m\x1b[60;D\x1b[K", '')

    # SLOTS
    telnet_session.sendline('debug hal show platform deviceInfo')
    telnet_session.expect('debug hal show platform deviceInfo')
    telnet_session.expect('\S+\s*#\s*$')
    info += '           ┌───────┐\n' \
            '           │ Слоты │\n' \
            '           └───────┘\n'
    info += str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
        "\x1b[m\x1b[60;D\x1b[K", '')
    return info
