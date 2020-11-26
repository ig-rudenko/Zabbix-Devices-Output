import pexpect
from re import findall, sub
import os
import sys
import textfsm
from func.intf_view import interface_normal_view

root_dir = os.path.join(os.getcwd(), os.path.split(sys.argv[0])[0])


def show_interfaces(telnet_session) -> list:
    telnet_session.sendline('show interfaces configuration')
    port_state = ''
    while True:
        match = telnet_session.expect(['More: <space>', '#', pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8'))
        port_state += page.strip()
        if match == 0:
            telnet_session.sendline(' ')
        elif match == 1:
            break
        else:
            print("    Ошибка: timeout")
            break

    # Description
    with open(f'{root_dir}/templates/int_des_alcatel_linksys.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_state = int_des_.ParseText(port_state)  # Ищем интерфейсы
    telnet_session.sendline('show int des')
    telnet_session.expect('#')
    port_desc = ''
    while True:
        match = telnet_session.expect(['More: <space>', '#', pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8'))
        port_desc += page.strip()
        if match == 0:
            telnet_session.sendline(' ')
        elif match == 1:
            break
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/int_des_alcatel_linksys2.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_des = int_des_.ParseText(port_desc)  # Ищем интерфейсы

    # Ищем состояние порта
    telnet_session.sendline('show int status')
    telnet_session.expect('#')
    port_desc = ''
    while True:
        match = telnet_session.expect(['More: <space>', '#', pexpect.TIMEOUT])
        page = str(telnet_session.before.decode('utf-8'))
        port_desc += page.strip()
        if match == 0:
            telnet_session.sendline(' ')
        elif match == 1:
            telnet_session.sendline('exit')
            break
        else:
            print("    Ошибка: timeout")
            break
    with open(f'{root_dir}/templates/int_des_alcatel_linksys_link.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_link = int_des_.ParseText(port_desc)  # Ищем интерфейсы

    result = []
    for postition, line in enumerate(result_port_state):
        result.append([line[0],  # interface
                       line[1],  # admin status
                       result_port_link[postition][0],  # link
                       result_port_des[postition][0]])  # description
    return result
