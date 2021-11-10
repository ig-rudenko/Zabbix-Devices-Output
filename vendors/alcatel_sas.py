import sys
import textfsm
from core.commands import send_command as sendcmd


def send_command(session, command: str, prompt: str = r'\S+#\s*$', next_catch: str = None):
    return sendcmd(session, command, prompt, space_prompt=r'Press any key to continue \(Q to quit\)',
                   before_catch=next_catch)


def show_interfaces(session):
    port_desc = send_command(session, 'show port description')
    # Description
    with open(f'{sys.path[0]}/templates/interfaces/alcatel_sas_desc.template') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_desc = int_des_.ParseText(port_desc)  # Ищем интерфейсы

    port_stat = send_command(session, 'show port')
    # Status
    with open(f'{sys.path[0]}/templates/interfaces/alcatel_sas_port_stat.template') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result_port_stat = int_des_.ParseText(port_stat)  # Ищем интерфейсы

    result = []
    for line in result_port_stat:
        for desc_line in result_port_desc:
            if line[0] == desc_line[0]:
                result.append(
                    (
                        line[0],  # Интерфейс
                        line[2] if line[1] == 'Up' else 'Admin Down',  # Статус
                        desc_line[1].strip()  # Описание
                    )
                )

    return result
