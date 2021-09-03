import pexpect


def strip_text(text: str) -> str:
    return text.replace("[42D", '').replace("        ", '').replace(
            "\x1b[m\x1b[60;D\x1b[K", '').replace(
            '\x08\x08\x08\x08\x08\x08\x08\x08\x08\x08          \x08\x08\x08\x08\x08\x08\x08\x08\x08\x08',
            '').replace('[81D[32C[80D[27C[1A[J', '').replace('[81D[35C', '').replace('[81D[34C', '').strip()


def format_command(command: str) -> str:
    symbols = ['.', '|', '?', '(', ')', '[', ']', '+', '*']
    for letter in command:
        if letter in symbols:
            command = command.replace(letter, f'\\'+letter)
    return command


def send_command(session, command: str, prompt: str, space_prompt: str = None, before_catch: str = None) -> str:
    output = ''
    session.sendline(command)   # Отправляем команду
    session.expect(command[-30:])  # Считываем введенную команду с поправкой по длине символов
    if before_catch:
        session.expect(before_catch)
    if space_prompt:    # Если необходимо постранично считать данные, то создаем цикл
        while True:
            match = session.expect(
                [
                    prompt,             # 0 - конец
                    space_prompt,       # 1 - далее
                    pexpect.TIMEOUT     # 2
                ]
            )
            output += strip_text(str(session.before.decode('utf-8')))   # Убираем лишние символы
            if match == 0:
                break
            elif match == 1:
                session.send(" ")  # Отправляем символ пробела, для дальнейшего вывода
                output += '\n'
            else:
                print("    Ошибка: timeout")
                break
    else:   # Если вывод команды выдается полностью, то пропускаем цикл
        try:
            session.expect(prompt)
        except pexpect.TIMEOUT:
            pass
        output = session.before.decode('utf-8')
    return output
