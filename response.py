#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko

from wsgiref.util import FileWrapper


class Response:
    """
    Basic response class. Built in such a way to behave like a WSGI application
    itself
    """
    body_chunk_size = 1024

    def __init__(self, rv, static=False, status_no=200, mimetype='text/html'):
        self.rv = rv
        self.static = static
        self.status_no = status_no
        self.status = None
        self.mimetype = mimetype
        self.headers = {}

    def build_status(self):
        """Build status message from status code"""
        status_cls = self.status_no // 100
        if status_cls == 1:
            status_msg = ' Info'
        elif status_cls == 2:
            status_msg = ' OK'
        elif status_cls == 3:
            status_msg = ' Redirect'
        elif status_cls == 4:
            status_msg = ' Client Error'
        else:
            status_msg = ' Server Error'
        self.status = str(self.status_no) + status_msg

    def set_cookie(self, key, val, path='/'):
        self.headers['Set-Cookie'] = f'{key}={val}; Path={path}'

    def build_headers(self):
        self.headers['Content-Type'] = self.mimetype
        if 'text' in self.mimetype:
            self.headers['Content-Type'] += '; charset=utf-8'

    def prepare_rv(self):
        """Slice return value of handler into chunks to send them to WSGI
        server in a faster way """
        size = len(self.rv)
        index = 0
        res = []

        while size:
            if size > self.body_chunk_size:
                size -= self.body_chunk_size
                res.append(self.rv[index:index + self.body_chunk_size].encode())
                index += self.body_chunk_size
            else:
                size = 0
                res.append(self.rv[index:].encode())
                index = len(self.rv) - 1

        return res

    def __call__(self, environ, start_response):
        """Main wsgi call"""
        self.build_status()
        self.build_headers()
        headers = [(k, v) for k, v in self.headers.items()]
        start_response(self.status, headers)
        if not self.static:
            return self.prepare_rv()
        else:
            return FileWrapper(self.rv)

