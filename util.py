#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko
"""
Miscellaneous utility classes and functions
"""


import os
import pathlib
import random
import hashlib


class DirView:

    def __init__(self, server_dir, cwd):
        self.real_path = os.path.join(server_dir, cwd.strip('/'))
        self.cwd = cwd
        self.cur_dir, self.dirs, self.files = next(os.walk(self.real_path))
        self.parent = pathlib.Path(self.cwd).parent.as_posix() \
                        if self.cwd != '/' else  '/'

    def list_cum_dir(self):
        """for self.cwd = '/foo/bar/lol builds
        [
            ('/', '/'),
            ('foo', '/foo'),
            ('bar', '/foo/bar'),
            ('lol', '/foo/bar/lol')
        ]
        Used to display directory path in rendered template
        """
        cur_ful_dir = '/'
        res = [('/', cur_ful_dir),]

        for d in self.cwd.split('/'):
            if d:
                d = d + '/'
                cur_ful_dir += d
                res.append((d, cur_ful_dir))

        return res


class Client:
    """Wrapper for client to track current online users"""
    def __init__(self, u_name, server_dir, cwd='/'):
        self.server_dir = server_dir
        self.u_name = u_name
        self.cwd = cwd

    def real_cwd(self):
        return os.path.join(self.server_dir, self.u_name, self.cwd.strip('/'))

    def get_dir_view(self):
        return DirView(os.path.join(self.server_dir, self.u_name), self.cwd)


class Flash:
    """Wrapper for flash message"""
    level_to_css_cls = {
        1: "alert-info",
        2: "alert-warning",
        3: "alert-danger"
    }

    # all instances cached
    _flashes = []

    def __init__(self, msg, level=2):
        self.msg = msg
        self.level = level
        type(self)._flashes.append(self)

    @property
    def alert_cls(self):
        return self.level_to_css_cls.get(self.level, "alert-info")

    @classmethod
    def flashes(cls):
        return cls._flashes

    @classmethod
    def clear_flashes(cls):
        cls._flashes.clear()


class FlashManager:
    """Manager class for Flash instances"""

    flash_cls = Flash

    def get_flashes(self):
        return self.flash_cls.flashes()

    def flash(self, msg, level=2):
        return self.flash_cls(msg, level)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flash_cls.clear_flashes()


def derive_token():
    """Derive random token hash(rand_bits)"""
    return hashlib.sha256(str(random.getrandbits(64)).encode()).hexdigest()


def render_template(template_name, app, **kwargs):
    template = app.template_env.get_template(template_name)
    res = template.render(**kwargs)
    return res
