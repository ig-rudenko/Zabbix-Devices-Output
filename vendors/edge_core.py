import pexpect
from re import findall
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = sys.path[0]


def show_interfaces(telnet_session) -> list:
    telnet_session.sendline('show running-config')
    output = ''
    while True:
        match = telnet_session.expect(['---More---', '#', pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace(
            '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08',
            '')
        output += page.strip()
        if match == 0:
            telnet_session.sendline(' ')
        elif match == 1:
            break
        else:
            print("    Ошибка: timeout")
            break

    telnet_session.sendline('show interfaces status')
    telnet_session.expect('show interfaces status')
    des_output = ''
    while True:
        match = telnet_session.expect(['---More---', '#', pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8')).replace(
            '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08',
            '')
        des_output += page.strip()
        if match == 0:
            telnet_session.sendline(' ')
        elif match == 1:
            break
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/int_des_edge_core.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_des = int_des_.ParseText(des_output)  # Ищем интерфейсы

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
    return result


def show_device_info(telnet_session):
    info = ''
    # VERSION
    telnet_session.sendline('show system')
    telnet_session.expect('show system')
    telnet_session.expect('\S+#')
    info += str(telnet_session.before.decode('utf-8'))

    # SNMP
    telnet_session.sendline('show snmp')
    telnet_session.expect('show snmp\W+')
    info += '   ┌──────┐\n'
    info += '   │ SNMP │\n'
    info += '   └──────┘\n'
    while True:
        match = telnet_session.expect(['---More---', '#', pexpect.TIMEOUT])
        info += str(telnet_session.before.decode('utf-8'))
        if match == 0:
            telnet_session.sendline(' ')
            info += '\n'
        else:
            info += '\n'
            break
    return info
