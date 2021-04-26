import pexpect
from re import findall, sub
import sys
from core import textfsm
from core.intf_view import interface_normal_view


def send_command(session, command: str, prompt=None):
    if prompt is None:
        prompt = r"\S+#"
    session.sendline(command)
    output = ''
    while True:
        match = session.expect(
            [
                r"-- MORE --, next page: Space, next line: Enter, quit: Control-C",
                prompt,
                pexpect.TIMEOUT
            ]
        )
        output += str(session.before.decode('utf-8'))
        if match == 0:
            session.send(' ')
            output += '\n'
        if match >= 1:
            break
    return output


def show_interfaces(session) -> list:
    result = []
    raw_intf_status = send_command(session, 'show interfaces brief')
    with open(f'{sys.path[0]}/templates/interfaces/procurve_status.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
    intf_status = int_des_.ParseText(raw_intf_status)  # Ищем интерфейсы
    # with open(f'{sys.path[0]}/templates/interfaces/procurve_description.template', 'r') as template_file:
    #     description_template = textfsm.TextFSM(template_file)   # Шаблон поиска описаний портов
    for line in intf_status:
        port = findall(r'[ABCD]*\d+', line[0])[0]
        port_output = send_command(session, f'show interfaces ethernet {port}')
        # descr = description_template.ParseText(port_output)  # Ищем описание портов
        descr = findall(r'Name\s*(:\s*\S*)\W+Link', port_output)
        result.append(
            [
                line[0],
                "Up" if line[1] == "Yes" else "Down",
                line[2],
                descr[0][1:] if descr else ''
            ]
        )
    return result


def get_device_info(session):
    version = ''
    version += send_command(session, 'show system-information')
    return version
