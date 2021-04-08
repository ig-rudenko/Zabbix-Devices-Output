import pexpect
from re import findall, sub
import sys
from core import textfsm
from core.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_interfaces(telnet_session, privilege_mode_password: str) -> list:
    telnet_session.sendline('\n')
    level = telnet_session.expect(
        [
            r'\(cfg\)#$',   # 0 - привилегированный режим
            r'>$'           # 1 - режим просмотра
        ]
    )
    if level:
        telnet_session.sendline('enable')
        telnet_session.expect('[Pp]ass')
        telnet_session.sendline(privilege_mode_password)
        telnet_session.expect(r'\(cfg\)#$')
    telnet_session.sendline('show port')
    output = ''
    while True:
        match = telnet_session.expect(
            [
                r'\(cfg\)#$',           # 0 - конец списка
                "----- more -----",     # 1 - продолжаем
                pexpect.TIMEOUT         # 2
            ]
        )
        page = str(telnet_session.before.decode('utf-8')).replace("[42D", '').replace(
            "        ", '')
        output += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")    # отправляем символ пробела, без '\n'
            output += '\n'
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/interfaces/zte.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return result


def show_mac(telnet_session, interfaces: list, interface_filter: str):
    intf_to_check = []
    mac_output = ''
    not_uplinks = True if interface_filter == 'only-abonents' else False

    for line in interfaces:
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
        telnet_session.sendline(f'show mac all-types port {intf[0]}')
        if telnet_session.expect([r'6,DHCP', 'No MAC']):
            separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
            mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n No MAC address exists!\n\n"
            continue
        mc_output = ''
        while True:
            match = telnet_session.expect(
                [
                    r'\S+\(cfg\)#$|\S+>$',        # 0 - конец списка
                    r"----- more ----- Press Q or Ctrl\+C to break -----",     # 1 - далее
                    pexpect.TIMEOUT]        # 2
            )
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
        separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
        mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n{mc_output}\n\n"
    if not intf_to_check:
        return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
    return mac_output


def show_device_info(telnet_session):

    def send_command(command: str):
        telnet_session.sendline(command)
        telnet_session.expect(command)
        telnet_session.expect(r'\S+\(cfg\)#$|\S+>$')
        return telnet_session.before.decode('utf-8').strip()

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
