#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko

import os
from functools import partial

from request import Request
from response import Response
from util import render_template as _render_template
from defaults import TEMPLATE_ENV


class App:

    template_env = TEMPLATE_ENV
    request_cls = Request
    response_cls = Response

    def __init__(self, statics_dir='static'):
        self._route_handlers = {}
        self._err_handlers = {}
        self._statics_dir = statics_dir
        self._sessions = {}

    def route(self, link):
        """Method to register view functions"""

        def wrapper(f):
            self._route_handlers[link] = f
            return f

        return wrapper

    def err(self, err_no):
        """Method to register error handle functions"""

        def wrapper(f):
            self._err_handlers[err_no] = f
            return f

        return wrapper

    def __call__(self, environ, start_response):
        """It is a common practice to separate __call__ from actual call to
        WSGI application in order to leave space to possible middleware"""
        return self.wsgi_call(environ, start_response)

    def open_static(self, path):
        path = path.lstrip('/')
        path = os.path.join(self._statics_dir, path)
        if os.path.isfile(path):
            fp = open(path, 'rb')
            return fp
        return None

    def is_static_requested(self, url):
        name = url.split('/')[-1]
        return '.' in name

    def url_for(self, request, location):
        # TODO: how to support another schemas
        #       and whether they has to be supported at all?
        return f'http://{request.server_addr}/{location.strip("/")}'

    def redirect(self, location, code=302):
        response = self.response_cls(
            "<!DOCTYPE html>\n"
            "<title>Redirecting</title>\n"
            "<p>Redirecting <a href={}>here</a></p>".format(location),
            status_no=code)
        response.headers['Location'] = location
        return response

    def respond_with_file_download(self, file_path):
        if os.path.isfile(file_path):
            f = open(file_path, 'rb')
            file_size = os.path.getsize(file_path)
            _, file_name = os.path.split(file_path)
            response = self.response_cls(f, static=True,
                                         mimetype='application/octet-stream')
            response.headers['Content-Disposition'] = f'attachment; ' \
                                                      f'filename={file_name}'
            response.headers['Content-Length'] = str(file_size)
            return response
        else:
            raise RuntimeError(f'Attempted to download '
                               f'unknown file: {file_path}')

    def build_response(self, cur_request):
        """Build response for given request"""
        # cur_request = self.request_cls(environ)
        path = cur_request.path_info
        err_rv = self._err_handlers[404]()

        if self.is_static_requested(path):
            fp = self.open_static(path)
            if fp is not None:
                response = self.response_cls(fp, static=True,
                                             mimetype='image/jpeg')
            else:
                response = self.response_cls(err_rv, status_no=404)

        else:
            handler = self._route_handlers.get(path)
            if not handler:
                response = self.response_cls(err_rv, status_no=404)
            else:
                rv = handler(cur_request)
                response = self.ensure_response_from_handler(rv)
        return response

    def ensure_response_from_handler(self, rv):
        """Handler may return response body only as well as entire response
        (as result of redirect function for example)"""
        if isinstance(rv, (str, bytes)):
            return self.response_cls(rv)
        elif isinstance(rv, self.response_cls):
            return rv

    def wsgi_call(self, environ, start_response):
        # parse environ into Request cls to reach required data in a more
        # convenient way
        cur_request = self.request_cls(environ)

        # make use of registered route handlers and build final response
        response = self.build_response(cur_request)

        # delegate response execution to a Response class, which in turn
        # behave itself as a WSGI app
        return response(environ, start_response)


render_template = partial(_render_template, app=App)
