
import sys
import textfsm
from core.commands import send_command as sendcmd


def send_command(session, command: str, prompt: str = r'\S+#\s*$', next_catch: str = None):
    return sendcmd(session, command, prompt, space_prompt=r'More: <space>,  Quit: q, One line: <return> ',
                   before_catch=next_catch)


def show_interfaces(telnet_session) -> list:
    port_state = send_command(
        session=telnet_session,
        command='show interfaces configuration'
    )
    # Description
    with open(f'{sys.path[0]}/templates/interfaces/alcatel_linksys.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_state = int_des_.ParseText(port_state)  # Ищем интерфейсы

    port_desc = send_command(
        session=telnet_session,
        command='show interfaces description'
    )
    with open(f'{sys.path[0]}/templates/interfaces/alcatel_linksys2.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_des = int_des_.ParseText(port_desc)  # Ищем интерфейсы

    # Ищем состояние порта
    port_status = send_command(
        session=telnet_session,
        command='show interfaces status'
    )
    with open(f'{sys.path[0]}/templates/interfaces/alcatel_linksys_link.template', 'r') as template_file:
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
