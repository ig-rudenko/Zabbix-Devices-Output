from re import findall, sub
import sys
import textfsm
from core.misc import interface_normal_view
from core.commands import send_command as sendcmd
from core.misc import filter_interface_mac


def send_command(session, command: str, privilege_mode_password: str, prompt: str = r'\S+#', next_catch: str = None):
    if not enable_admin(session, privilege_mode_password):
        return ''
    return sendcmd(session, command, prompt, before_catch=next_catch)


def enable_admin(session, privilege_mode_password: str) -> bool:
    """
    Повышает уровень привилегий до уровня администратора
    :param session: TELNET Сессия
    :param privilege_mode_password: пароль от уровня администратора
    :return: True/False
    """
    status = True
    session.sendline('enable admin')
    if not session.expect(
        [
            "[Pp]ass",           # 0 - ввод пароля
            r"You already have"  # 1 - уже администратор
        ]
    ):
        session.sendline(privilege_mode_password)
    while session.expect(['#', 'Fail!']):
        session.sendline('\n')
        print('privilege_mode_password wrong!')
        status = False
    if status:
        session.sendline('disable clipaging')   # отключение режима постраничного вывода
        session.expect('#')
    return status


def show_interfaces(session, privilege_mode_password: str) -> list:
    if not enable_admin(session, privilege_mode_password):
        return []
    session.sendline("show ports des")
    session.expect('#')
    output = session.before.decode('utf-8')
    with open(f'{sys.path[0]}/templates/interfaces/d-link.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return [
        [
            line[0],    # interface
            line[2].replace('LinkDown', 'down') if 'Enabled' in line[1] else 'admin down',  # status
            line[3]     # desc
        ]
        for line in result
    ]


def show_mac(session, interfaces: list, interface_filter: str) -> str:
    mac_output = ''

    # Оставляем только необходимые порты для просмотра MAC
    intf_to_check, status = filter_interface_mac(interfaces, interface_filter)
    if not intf_to_check:
        return status

    for intf in intf_to_check:
        session.sendline(f'show fdb port {interface_normal_view(intf[0])}')
        session.expect('#')
        mc_output = sub(r'[\W\S]+VID', 'VID', str(session.before.decode('utf-8')))
        mc_output = sub(r'Total Entries[\s\S]+', ' ', mc_output)
        separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[1]})')
        mac_output += f"\n    Интерфейс: {intf[0]} ({intf[1]})\n    {separator_str}\n{mc_output}"
    if not intf_to_check:
        return f'Не найдены запрашиваемые интерфейсы на данном оборудовании!'
    return mac_output


def show_device_info(session, privilege_mode_password: str):
    info = ''
    if not enable_admin(session, privilege_mode_password):
        return

    # VERSION
    session.sendline('show switch')
    session.expect(r'Command: show switch')
    if session.expect([r'\S+#', r'Previous Page']):
        session.sendline('q')
    info += session.before.decode('utf-8')
    info += '\n'

    # CPU
    session.sendline('show utilization cpu')
    session.expect(r'Command: show utilization cpu\W+')
    if session.expect([r'\S+#', r'Previous Page']):
        session.sendline('q')
    info += '   ┌──────────────┐\n'
    info += '   │ ЗАГРУЗКА CPU │\n'
    info += '   └──────────────┘\n'
    info += session.before.decode('utf-8')
    return info


def show_cable_diagnostic(session, privilege_mode_password: str):
    info = ''
    enable_admin(session, privilege_mode_password)

    # CABLE_DIAGNOSTIC
    session.sendline('cable_diag ports all')
    if session.expect([r'Perform Cable Diagnostics ...\W+', 'Available commands:']):
        info = 'Данное устройство не поддерживает диагностику портов'
    else:
        session.expect(r'\S+#')
        info += '''
                ┌─────────────────────┐
                │ Диагностика кабелей │
                └─────────────────────┘
    
        Pair Open — конец линии (либо обрыв) на растоянии ХХ метров
        Link Up, длинна ХХ метров
        Link Down, OK — нельзя измерить длинну кабеля (но нагрузка есть)
        Link Down, No Cable — нет кабеля
    
        '''
        info += session.before.decode('utf-8')
    return info


def show_vlans(session, interfaces: list, privilege_mode_password: str) -> tuple:

    def range_to_numbers(ports_string: str) -> list:
        ports_split = ports_string.split(',')
        res_ports = []
        for p in ports_split:
            if '-' in p:
                port_range = list(range(int(p.split('-')[0]), int(p.split('-')[1]) + 1))
                for pr in port_range:
                    res_ports.append(int(pr))
            else:
                res_ports.append(int(p))

        return sorted(res_ports)

    enable_admin(session, privilege_mode_password)
    session.sendline('show vlan')
    session.expect('#', timeout=20)
    output = session.before.decode('utf-8')
    with open(f'{sys.path[0]}/templates/vlans_templates/d-link.template', 'r') as template_file:
        vlan_templ = textfsm.TextFSM(template_file)
        result_vlan = vlan_templ.ParseText(output)
    # сортируем и выбираем уникальные номера портов из списка интерфейсов
    port_num = set(sorted([int(findall(r'\d+', p[0])[0]) for p in interfaces]))

    # Создаем словарь, где ключи это кол-во портов, а значениями будут вланы на них
    ports_vlan = {num: [] for num in range(1, len(port_num)+1)}

    vlans_info = ''     # Информация о имеющихся vlan
    for vlan in result_vlan:
        # Если имя vlan не равно его vid
        if vlan[0] != vlan[1]:
            vlans_info += f'VLAN: {vlan[0]} ({vlan[1]})\n'
        else:
            vlans_info += f'VLAN: {vlan[0]}\n'
        for port in range_to_numbers(vlan[2]):
            # Добавляем вланы на порты
            ports_vlan[port].append(vlan[0])
    interfaces_vlan = []    # итоговый список (интерфейсы и вланы)

    for line in interfaces:
        max_letters_in_string = 20  # Ограничение на кол-во символов в одной строке в столбце VLAN's
        vlans_compact_str = ''  # Строка со списком VLANов с переносами
        line_str = ''
        for part in ports_vlan[int(findall(r'\d+', line[0])[0])]:
            if len(line_str) + len(part) <= max_letters_in_string:
                line_str += f'{part},'
            else:
                vlans_compact_str += f'{line_str}\n'
                line_str = f'{part},'
        else:
            vlans_compact_str += line_str[:-1]
        interfaces_vlan.append(line + [vlans_compact_str])
    return vlans_info, interfaces_vlan
