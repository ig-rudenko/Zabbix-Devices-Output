import pexpect
from core.commands import send_command
import textfsm
import sys


def send_cmd(session, command, prompt=r'-> $', ):
    return send_command(session, command, prompt, space_prompt='--- more --- ')


def show_interfaces(session):
    output = send_cmd(session, 'get system')
    with open(f'{sys.path[0]}/templates/interfaces/juniper.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return [
        [
            line[0],    # interface
            line[2].lower() if 'up' in line[1].lower() else 'admin down',  # status
            line[3]     # desc
        ]
        for line in result if not line[0].startswith('bgroup')
    ]
