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
        return f'TengigabitEthernet {interface_number[0][0]}'
    else:
        return interface
