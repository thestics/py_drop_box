#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko


import sqlite3
import logging as log


log.getLogger()


def init_db(path):
    """Init routine"""
    try:
        db_manager = DB(path)
        q = """create table USERS (login text, pass_hash text)"""
        db_manager.curs.execute(q)
        db_manager.conn.commit()
    except Exception:
        pass


class DB:

    def __init__(self, path):
        self.conn = sqlite3.connect(path)
        self.curs = self.conn.cursor()

    def _fetch_data_by_uname(self, u_name):
        q = """select * from USERS where login=?"""
        self.curs.execute(q, (u_name,))
        return self.curs.fetchone()

    def try_register(self, u_name, pass_hash):
        """
        Try register user with provided user_name.

        :param u_name:
        :param pass_hash:
        :return: bool Attempt status (False if username taken)
        """
        if not self._fetch_data_by_uname(u_name):
            q = """insert into USERS values (?, ?)"""
            self.curs.execute(q, (u_name, pass_hash))
            self.conn.commit()
            return True
        return False

    def try_login(self, u_name, pass_hash):
        """
        For provided credentials answer if they match corresponding data
        in db

        :param u_name: user_name
        :param pass_hash: password hash (sha512)
        :return:
        """
        query_res = self._fetch_data_by_uname(u_name)

        # query res is non-empty and retrieved hash matches provided one
        return query_res and query_res[1] == pass_hash
