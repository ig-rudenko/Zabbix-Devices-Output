import pexpect
import sys
from core import textfsm

root_dir = sys.path[0]


def send_command(session, command: str, prompt: str = r'\S+#\s*$', next_catch: str = None):
    session.sendline(command)
    session.expect(command)
    if next_catch:
        session.expect(next_catch)
    output = ''
    while True:
        match = session.expect(
            [
                r'More: <space>,  Quit: q, One line: <return> ',
                prompt,
                pexpect.TIMEOUT
            ]
        )
        output += session.before.decode('utf-8').strip()
        if match == 0:
            session.send(' ')
        elif match == 1:
            break
        else:
            print("    Ошибка: timeout")
            break
    return output


def show_interfaces(telnet_session) -> list:
    port_state = send_command(
        session=telnet_session,
        command='show interfaces configuration'
    )
    # Description
    with open(f'{root_dir}/templates/int_des_alcatel_linksys.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_state = int_des_.ParseText(port_state)  # Ищем интерфейсы

    port_desc = send_command(
        session=telnet_session,
        command='show interfaces description'
    )
    with open(f'{root_dir}/templates/int_des_alcatel_linksys2.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_des = int_des_.ParseText(port_desc)  # Ищем интерфейсы

    # Ищем состояние порта
    port_status = send_command(
        session=telnet_session,
        command='show interfaces status'
    )
    with open(f'{root_dir}/templates/int_des_alcatel_linksys_link.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_link = int_des_.ParseText(port_status)  # Ищем интерфейсы

    result = []
    for postition, line in enumerate(result_port_state):
        result.append([line[0],  # interface
                       line[1],  # admin status
                       result_port_link[postition][0],  # link
                       result_port_des[postition][0]])  # description
    return result


def show_device_info(telnet_session):
    info = ''
    info += send_command(
        session=telnet_session,
        command='show system'
    )
    info += '''
    ┌──────────────┐
    │ ЗАГРУЗКА CPU │
    └──────────────┘
'''
    info += send_command(
        session=telnet_session,
        command='show cpu utilization'
    )
    return info


