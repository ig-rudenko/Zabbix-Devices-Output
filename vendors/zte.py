import pexpect
from re import findall, sub
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_interfaces(telnet_session) -> list:
    telnet_session.sendline('enable')
    telnet_session.expect('[Pp]ass')
    telnet_session.sendline('sevaccess')
    telnet_session.expect('#')
    telnet_session.sendline('show port')
    output = ''
    while True:
        match = telnet_session.expect([r'#$', "----- more -----", pexpect.TIMEOUT])
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
    with open(f'{root_dir}/templates/int_des_zte.template', 'r') as template_file:
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
        separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
        mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n{mc_output}\n\n"
    if not intf_to_check:
        return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
    return mac_output


def show_device_info(telnet_session):
    pass
