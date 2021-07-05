import sqlite3
import sys
import os
from tabulate import tabulate

db_path = f'{sys.path[0]}/db/database.db'
if not os.path.exists(os.path.split(db_path)[0]):
    os.makedirs(os.path.split(db_path)[0])


class ConnectionDB(object):
    def __init__(self, database):
        self.database = database

    def __enter__(self):
        try:
            self.connection = sqlite3.connect(self.database)
            self.cursor = self.connection.cursor()
        except sqlite3.Error as db_err:
            print(f'Error: {db_err}')
            raise db_err
        return self.cursor

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        If __exit__ returns True, the exception is suppressed.
        """
        self.cursor.close()
        if self.connection:
            self.connection.close()
        if exc_type:
            print(f'Exception type: {exc_type}')
            print(f'Value: {exc_val}')
            print(f'Traceback: {exc_tb}')
        else:
            return True

    def __call__(self, function):
        def inner(*args, **kwargs):
            with self as cursor:
                inner.__setattr__('cursor', cursor)
                return_value = function(*args, **kwargs)
                self.connection.commit()
                return return_value

        return inner


class DataBase:
    def __init__(self):
        self.create_table()

    @ConnectionDB(database=db_path)
    def create_table(self):
        cursor = self.create_table.cursor
        try:
            cursor.execute('''
                create table equipment (
                    ip              text not NULL primary key,
                    device_name     text not NULL,
                    vendor          text,
                    auth_group      text,
                    default_potocol text,
                    model           text
                );
            ''')
            return True
        except sqlite3.OperationalError:
            # Данная таблица уже создана
            return True
        except:
            return False

    @ConnectionDB(database=db_path)
    def add_data(self, data: list) -> None:
        """
        Принимаем на вход список кортежей [ (ip, device_name, vendor, auth_group, default_protocol, model) ]
        """
        for row in data:
            try:
                self.add_data.cursor.execute(
                    'insert into equipment values (?, ?, ?, ?, ?, ?)',
                    row
                )
            except sqlite3.IntegrityError:
                # Данная строка уже имеется
                pass

    @ConnectionDB(database=db_path)
    def show_table(self):
        self.show_table.cursor.execute(
            "select * from equipment;"
        )
        print(
            tabulate(
                self.show_table.cursor.fetchall(),
                headers=['ip', 'device_name', 'vendor', 'auth_group', 'default_protocol', 'model'],
                tablefmt="presto",
                showindex="always"
            )
        )

    @ConnectionDB(database=db_path)
    def get_table(self):
        self.get_table.cursor.execute(
            "select * from equipment;"
        )
        return self.get_table.cursor.fetchall()

    @ConnectionDB(database=db_path)
    def get_item(self, ip: str = None, device_name: str = None):
        if ip:
            self.get_item.cursor.execute(
                f"select * from equipment where ip = '{ip}';"
            )
        elif device_name:
            self.get_item.cursor.execute(
                f"select * from equipment where device_name = '{device_name}';"
            )
        else:
            return False
        return self.get_item.cursor.fetchall()

    @ConnectionDB(database=db_path)
    def execute(self, command):
        try:
            self.execute.cursor.execute(command)
            return self.execute.cursor.fetchall()
        except sqlite3.OperationalError as OperationalError:
            print(f'sqlite3.OperationalError: {command}\n{OperationalError}')
            return False
        except Exception as error:
            raise error

    @ConnectionDB(database=db_path)
    def update(self, ip: str, **kwargs):
        kv = []
        for key in kwargs:
            kv.append(f"{key}='{kwargs[key]}'")
        string = ','.join(kv)
        self.execute(f"""
                UPDATE equipment SET {string} WHERE ip='{ip}'
        """)
