from re import findall
import sys
import textfsm
from core.commands import send_command as sendcmd


def send_command(session, command: str, prompt=r"\S+#"):
    return sendcmd(session, command, prompt, expect_command=False,
                   space_prompt=r"-- MORE --, next page: Space, next line: Enter, quit: Control-C")


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
                line[2].lower() if line[1] == "Yes" else "admin down",
                descr[0][1:] if descr else ''
            ]
        )
    return result


def get_device_info(session):
    version = ''
    version += send_command(session, 'show system-information')
    return version
