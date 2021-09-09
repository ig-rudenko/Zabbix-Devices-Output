from re import findall


def interface_normal_view(interface) -> str:
    """
    Приводит имя интерфейса к виду принятому по умолчанию для коммутаторов\n
    Например: Eth 0/1 -> Ethernet0/1
              GE1/0/12 -> GigabitEthernet1/0/12\n
    :param interface:   Интерфейс в сыром виде (raw)
    :return:            Интерфейс в общепринятом виде
    """
    interface = str(interface)
    interface_number = findall(r'(\d+([/\\]?\d*)*)', str(interface))
    if bool(findall('^[Ee]t', interface)):
        return f"Ethernet {interface_number[0][0]}"
    elif bool(findall('^[Ff]a', interface)):
        return f"FastEthernet {interface_number[0][0]}"
    elif bool(findall('^[Gg][ieE]', interface)):
        return f"GigabitEthernet {interface_number[0][0]}"
    elif bool(findall('^\d+', interface)):
        return findall('^\d+', interface)[0]
    elif bool(findall('^[Tt]e', interface)):
        return f'TenGigabitEthernet {interface_number[0][0]}'
    else:
        return interface


def filter_interface_mac(interfaces: list, interface_filter: str) -> tuple:
    intf_to_check = []  # Интерфейсы для проверки
    not_uplinks = True if interface_filter == 'only-abonents' else False
    for line in interfaces:
        if (
                (not not_uplinks and bool(findall(interface_filter, line[3])))  # интерфейсы по фильтру
                or (not_uplinks and  # ИЛИ все интерфейсы, кроме:
                    'SVSL' not in line[2].upper() and  # - интерфейсов, которые содержат "SVSL"
                    'POWER_MONITORING' not in line[2].upper())  # - POWER_MONITORING
                and not ('down' in line[1].lower() and not line[2])  # - пустые интерфейсы с LinkDown
                and 'admin down' not in line[1].lower()  # И только интерфейсы со статусом admin up
                and 'VL' not in line[0].upper()  # И не VLAN'ы
        ):  # Если описание интерфейсов удовлетворяет фильтру
            intf_to_check.append([line[0], line[2]])

    status = 'done'
    if not intf_to_check:
        if not_uplinks:
            status = 'Порты абонентов не были найдены либо имеют статус admin down (в этом случае MAC\'ов нет)'
        else:
            status = f'Ни один из портов не прошел проверку фильтра "{interface_filter}" ' \
                   f'либо имеет статус admin down (в этом случае MAC\'ов нет)'
    return intf_to_check, status
