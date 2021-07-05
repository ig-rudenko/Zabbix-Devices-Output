import pexpect
from re import findall, sub
import sys
import textfsm
from core.intf_view import interface_normal_view

root_dir = sys.path[0]


def login(session, privilege_mode_password: str):
    huawei_type = 'huawei-2326'
    session.sendline('super')
    v = session.expect(
        [
            'Unrecognized command|Now user privilege is 3 level',     # 0 - huawei-2326
            '[Pp]ass',                  # 1 - huawei-2403 повышение уровня привилегий
            'User privilege level is'   # 2 - huawei-2403 уже привилегированный
        ]
    )
    if v == 1:
        session.sendline(privilege_mode_password)
    if v >= 1:
        huawei_type = 'huawei-2403'
    if session.expect(
            [
                r'<\S+>',   # 0 - режим просмотра
                r'\[\S+\]'  # 1 - режим редактирования
            ]
    ):  # Если находимся в режиме редактирования, то понижаем до режима просмотра
        session.sendline('quit')
        session.expect(r'<\S+>$')
    return huawei_type


def send_command(session, command: str, prompt=None) -> str:
    if prompt is None:
        prompt = r'<\S+>$'
    session.sendline(command)
    session.expect(command)
    output = ''
    while True:
        match = session.expect(
            [
                "  ---- More ----",         # 0 - продолжаем
                prompt,                     # 1 - конец
                "Unrecognized command",     # 2 - данная команда не найдена
                pexpect.TIMEOUT             # 3
            ]
        )
        output += str(session.before.decode('utf-8'))
        if match == 0:
            session.send(' ')
            output += '\n'
        if match >= 1:
            break
    return output


def show_mac_huawei(telnet_session, interfaces: list, interface_filter: str, privilege_mode_password: str) -> str:
    intf_to_check = []  # Интерфейсы для проверки
    mac_output = ''  # Вывод MAC

    huawei_type = login(telnet_session, privilege_mode_password)

    not_uplinks = True if interface_filter == 'only-abonents' else False

    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[2].upper() and  # - интерфейсов, которые содержат "SVSL"
                    'HUAWEI, QUIDWAY' not in line[2].upper() and  # - "заглушек" типа "HUAWEI, Quidway Series
                    'POWER_MONITORING' not in line[2].upper())  # - POWER_MONITORING
                and 'down' not in line[1].lower()  # И только интерфейсы со статусом admin up
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[2]])

    if not intf_to_check:
        if not_uplinks:
            return 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            return f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'

    for intf in intf_to_check:  # для каждого интерфейса
        if huawei_type == 'huawei-2326':
            telnet_session.sendline(f'display mac-address {interface_normal_view(intf[0])}')

        if huawei_type == 'huawei-2403':
            telnet_session.sendline(f'display mac-address interface {interface_normal_view(intf[0])}')
        separator_str = '─' * len(f'Интерфейс: {intf[1].strip()}')
        telnet_session.expect(f'{interface_normal_view(intf[0])}')

        mac_output += f'\n    Интерфейс: {intf[1].strip()}\n    {separator_str}\n'
        while True:
            match = telnet_session.expect(
                [
                    r'<\S+>$' if huawei_type == 'huawei-2326' else '  ---  ',   # 0 - конец вывода
                    "  ---- More ----",                                         # 1 - продолжаем
                    pexpect.TIMEOUT                                             # 2
                ]
            )
            page = str(telnet_session.before.decode('utf-8'))
            mac_output += page.strip()
            if match == 0:
                break
            elif match == 1:
                telnet_session.send(" ")
                mac_output += '\n'
            else:
                print("    Ошибка: timeout")
                break
        mac_output += '\n\n'
    return mac_output


def show_interfaces_split_version(session, privilege_mode_password: str) -> list:
    login(session, privilege_mode_password)  # Авторизируемся
    raw_descriptions = send_command(session, 'display interface description')
    with open(f'{root_dir}/templates/interfaces/huawei-2326_descriptions.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
    descriptions = int_des_.ParseText(raw_descriptions)  # Ищем интерфейсы
    raw_status = send_command(session, 'display interface brief')
    with open(f'{root_dir}/templates/interfaces/huawei-2326_status.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
    status = int_des_.ParseText(raw_status)  # Ищем интерфейсы
    result = []
    # Далее объединяем два массива в один: Интерфейс, Состояние + Описание
    for line in status:
        for desc in descriptions:
            if line[0] == desc[0]:
                # Выводим физическое состояние интерфейса, если он admin down или standby
                if line[1] == '*down' or line[1] == '^down':
                    result.append([line[0], line[1], desc[1].strip()])
                elif line[1] == line[2]:
                    result.append([line[0], line[2], desc[1].strip()])
                else:
                    # Если вывод не стандартный, то объединяем два значения
                    result.append([line[0], f'{line[1]}/{line[2]}', desc[1].strip()])
    return result


def show_interfaces(telnet_session, privilege_mode_password: str) -> list:
    """
        Обнаруживаем интерфейсы на коммутаторе типа Huawei
    :param telnet_session:              залогиненная сессия
    :param privilege_mode_password:     пароль от привилегированного режима
    :return:                            Кортеж (список интерфейсов, тип huawei)
    """

    huawei_type = login(telnet_session, privilege_mode_password)
    output = ''
    if huawei_type == 'huawei-2403':
        output = send_command(telnet_session, 'display brief interface')
    if huawei_type == 'huawei-2326':
        output = send_command(telnet_session, 'display interface description')

    with open(f'{root_dir}/templates/interfaces/{huawei_type}.template', 'r') as template_file:
        int_des_ = textfsm.TextFSM(template_file)
        result = int_des_.ParseText(output)  # Ищем интерфейсы
    return [line for line in result if not line[0].startswith('NULL') and not line[0].startswith('V')]


def show_device_info(telnet_session, privilege_mode_password: str):

    version = ''

    huawei_type = login(telnet_session, privilege_mode_password)

    if huawei_type == 'huawei-2403':
        # CPU
        version = f"""
{send_command(telnet_session, 'display version')}
        ┌──────────────┐
        │ ЗАГРУЗКА CPU │
        └──────────────┘
{send_command(telnet_session, 'display cpu')}
        ┌───────────────────────────┐
        │ MAC адрес, Серийный номер │
        └───────────────────────────┘
{send_command(telnet_session, 'display device manuinfo')}
        ┌──────────────┐
        │    MEMORY    │
        └──────────────┘
{send_command(telnet_session, 'display memory')}
        """

    if huawei_type == 'huawei-2326':
        version = f"""
{send_command(telnet_session, 'display version')}
        ┌─────────────┐
        │ Температура │
        └─────────────┘
{send_command(telnet_session, 'display environment')}
        ┌───────────┐
        │ MAC адрес │
        └───────────┘
{send_command(telnet_session, 'display bridge mac-address')}
        ┌────────────┐
        │ Охлаждение │
        └────────────┘
{send_command(telnet_session, 'display fan verbose')}

    ┌                                    ┐
    │ Расширенная техническая информация │
    └                                    ┘
                      ▼
"""
        telnet_session.sendline('display elabel')
        telnet_session.expect('display elabel')
        while True:
            m = telnet_session.expect(
                [
                    r'  ---- More ----',    # 0 - далее
                    r'<\S+>',               # 1 - конец списка
                    pexpect.TIMEOUT         # 2
                ]
            )
            version += telnet_session.before.decode('utf-8')
            if not m:
                telnet_session.send(' ')
                version += '\n'
            else:
                break
    return version


def show_cable_diagnostic(telnet_session, privilege_mode_password):
    cable_diagnostic = ''
    huawei_type = login(telnet_session, privilege_mode_password)
    interfaces_list = show_interfaces(telnet_session, privilege_mode_password)
    telnet_session.sendline('system-view')
    telnet_session.expect('system-view')
    telnet_session.expect(r'\[\S+\]')

    if huawei_type == 'huawei-2326':
        # CABLE DIAGNOSTIC
        cable_diagnostic = '''
            ┌─────────────────────┐
            │ Диагностика кабелей │
            └─────────────────────┘

    Pair A/B/C/D   Четыре пары в сетевом кабеле

    Pair length    Длина сетевого кабеля:
                    ─ расстояние между интерфейсом и точкой разлома в случае возникновения неисправности;
                    ─ фактическая длина кабеля, когда он работает правильно.

    Pair state     Состояние сетевого кабеля:
                      Ok: указывает, что пара цепей нормально завершена.
                      Open: указывает, что пара цепей не завершена.
                      Short: указывает на короткое замыкание пары цепей.
                      Crosstalk: указывает на то, что пары цепей мешают друг другу.
                      Unknown: указывает, что пара цепей имеет неизвестную неисправность.


        '''
        for intf in interfaces_list:
            if 'NULL' not in intf[0] and 'Vlan' not in intf[0]:
                try:
                    separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}')
                    cable_diagnostic += f'    Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}\n' \
                                        f'    {separator_str}\n'
                    telnet_session.sendline(f'interface {interface_normal_view(intf[0])}')
                    telnet_session.expect(r'\S+]$')
                    telnet_session.sendline('virtual-cable-test')
                    if telnet_session.expect([r'continue \[Y/N\]', 'Error:']):
                        cable_diagnostic += 'Данный интерфейс не поддерживается\n\n'
                        telnet_session.sendline('quit')
                        telnet_session.expect(r'\S+]$')
                        continue
                    telnet_session.sendline('Y')
                    telnet_session.expect(r'\?Y\W*')
                    telnet_session.expect(r'\[\S+\]$')
                    cable_diagnostic += str(telnet_session.before.decode('utf-8'))
                    cable_diagnostic += '\n'
                    telnet_session.sendline('quit')
                    telnet_session.expect(r'\S+]$')
                except pexpect.TIMEOUT:
                    break

    if huawei_type == 'huawei-2403':
        # CABLE DIAGNOSTIC
        cable_diagnostic = '''
                ┌─────────────────────┐
                │ Диагностика кабелей │
                └─────────────────────┘


'''
        for intf in interfaces_list:
            if 'NULL' not in intf[0] and 'Vlan' not in intf[0] and not 'SVSL' in intf[2]:
                try:
                    separator_str = '─' * len(f'Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}')
                    cable_diagnostic += f'    Интерфейс: {intf[0]} ({intf[2]}) port status: {intf[1]}\n' \
                                        f'    {separator_str}\n'
                    telnet_session.sendline(f'interface {interface_normal_view(intf[0])}')
                    telnet_session.expect(r'\S+]$')
                    telnet_session.sendline('virtual-cable-test')
                    telnet_session.expect(r'virtual-cable-test\W+')
                    telnet_session.expect(r'\[\S+\d\]$')
                    cable_diagnostic += str(telnet_session.before.decode('utf-8'))
                    cable_diagnostic += '\n'
                    telnet_session.sendline('quit')
                    telnet_session.expect(r'\S+]$')

                except pexpect.TIMEOUT:
                    break
    return cable_diagnostic


def show_vlans(telnet_session, interfaces, privilege_mode_password: str) -> tuple:

    huawei_type = login(telnet_session, privilege_mode_password)

    result = []
    for line in interfaces:
        if not line[0].startswith('V') and not line[0].startswith('NU') and not line[0].startswith('A'):
            telnet_session.sendline(f"display current-configuration interface {interface_normal_view(line[0])}")
            # telnet_session.expect(f"interface {interface_normal_view(line[0])}")
            output = ''
            while True:
                match = telnet_session.expect(
                    [
                        r'>',
                        "  ---- More ----",
                        pexpect.TIMEOUT
                    ]
                )
                page = str(telnet_session.before.decode('utf-8'))
                output += page.strip()
                if match == 0:
                    break
                elif match == 1:
                    telnet_session.send(" ")
                    output += '\n'
                else:
                    print("    Ошибка: timeout")
                    break
            vlans_group = sub(r'(?<=undo).+vlan (.+)', '', output)   # Убираем строчки, где есть "undo"
            vlans_group = list(set(findall(r'vlan (.+)', vlans_group)))   # Ищем строчки вланов, без повторений
            switchport_mode = list(set(findall(r'port (hybrid|trunk|access)', output)))  # switchport mode
            max_letters_in_string = 20  # Ограничение на кол-во символов в одной строке в столбце VLAN's
            vlans_compact_str = ''      # Строка со списком VLANов с переносами
            line_str = ''
            for part in ','.join(switchport_mode + vlans_group).split(','):
                if len(line_str) + len(part) <= max_letters_in_string:
                    line_str += f'{part},'
                else:
                    vlans_compact_str += f'{line_str}\n'
                    line_str = f'{part},'
            else:
                vlans_compact_str += line_str[:-1]
            result.append(line + [vlans_compact_str])

    if huawei_type == 'huawei-2326':
        telnet_session.sendline(f"display vlan")
        telnet_session.expect(r"VID\s+Status\s+Property")
    else:
        telnet_session.sendline(f"display vlan all")
        telnet_session.expect(r"display vlan all")

    vlans_info = ''
    while True:
        match = telnet_session.expect(
            [
                r'>',
                "  ---- More ----",
                pexpect.TIMEOUT
            ]
        )
        page = str(telnet_session.before.decode('utf-8'))
        vlans_info += page.strip()
        if match == 0:
            break
        elif match == 1:
            telnet_session.send(" ")
            vlans_info += '\n'
        else:
            print("    Ошибка: timeout")
            break

    with open(f'{root_dir}/templates/vlans_templates/{huawei_type}_vlan_info.template', 'r') as template_file:
        vlans_info_template = textfsm.TextFSM(template_file)
        vlans_info_table = vlans_info_template.ParseText(vlans_info)  # Ищем интерфейсы

    return vlans_info_table, result
