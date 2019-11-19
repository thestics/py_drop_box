#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko


import urllib.parse
import re
import logging as log


log.getLogger()


class FileFromHTTPRequest:
    """Wrapper for wsgi.input to handle files upload from post request.

    Files are transmitted to the server through the body of HTTP request,
    enclosed in special file_bound string. To store this file, we can either
    load it entirely in the RAM or read it sequentially and write on disk
    right away. Although the second option is obviously better, we need to
    known exact file path before we can write to it. And latter can be derived
    only in view function body (functions, registered with @app.view decorator).
    And view function, in turn, requires request object as input parameter.
    So this class will wrap wsgi.input and via it view function will be able
    to download and write file on disk
    """
    read_chunk_size = 4 * 1024

    def __init__(self, fp, file_bound, body_size, name=None):
        self.fp = fp
        self.binary_file_bound = file_bound.encode()
        self.name = name
        self.body_size = body_size

    def save_to_file(self, file_path):
        try:
            with open(file_path, 'wb') as f:
                cur_size = self.body_size
                tail = b'\r\n--' + self.binary_file_bound + b'--\r\n'

                while cur_size:
                    if self.read_chunk_size > cur_size:
                        chunk = self.fp.read(cur_size).rstrip(tail)
                        cur_size = 0
                    else:
                        chunk = self.fp.read(self.read_chunk_size)
                        cur_size -= self.read_chunk_size
                    f.write(chunk)
                print(f'File saved to {file_path}')
        except Exception as e:
            log.error(e)
            return False
        return True


class Request:
    """Basic request class"""

    def __init__(self, environ):
        self.environ = environ
        self.headers = {k: v for k, v in self.environ.items()
                        if k.startswith('HTTP_')}
        self.wsgi_input = self.environ['wsgi.input']
        self.method = self.environ['REQUEST_METHOD']
        self.path_info = self.environ['PATH_INFO']
        self.content_length = self.environ['CONTENT_LENGTH']
        self.GET_params = {}
        self.POST_params = {}

        # TODO: multiple files may be transmitted in the same session, but
        #       here we do not consider reasonable to support it

        self.file = None
        self.parse_files()
        self.parse_get_post()

    def _extract_file_name(self, param):
        """Extracts filename from Content-Disposition parameter"""
        patt = re.compile(r'filename="(.+)"')
        match = patt.search(param)
        return match.group(1) if match else 'unknown_file'

    def parse_files(self):
        """Parse files transmitted in HTTP request if any"""
        content_type = self.environ.get('CONTENT_TYPE', '')

        if content_type.startswith('multipart/form-data'):
            file_bound = content_type.split('=')[1]
            header = {}

            file_body_length = int(self.content_length)
            while True:
                line = self.wsgi_input.readline()
                file_body_length -= len(line)
                decoded = line.decode().strip()
                if not decoded:
                    break

                # file bound differs from real file bound in two
                # leading hyphens (????!)
                if file_bound not in decoded:
                    key, value = decoded.split(': ')
                    header[key] = value

            self.file = FileFromHTTPRequest(self.wsgi_input,
                                            file_bound,
                                            file_body_length)
            self.file.name = self._extract_file_name(
                header['Content-Disposition']
            )

    def parse_get_post(self):
        """Parse get and post params"""
        self.GET_params = {}

        for raw_kv in urllib.parse.unquote(self.environ['QUERY_STRING']).split('&'):
            if raw_kv:
                k, v = raw_kv.split('=')
                self.GET_params[k] = v
        body_size = self.environ.get('CONTENT_LENGTH')

        # if we treated a from wsgi.input as an input for an uploaded file
        # we dont want to break file_pos pointer in it and parse it for post
        # params
        if body_size and not self.file:

            data = self.wsgi_input.read(int(body_size))
            data = urllib.parse.unquote(data.decode())
            data = urllib.parse.parse_qs(data)
            self.POST_params = {k: [p for p in v]
                                for k, v in data.items()}
        else:
            self.POST_params = {}

    @property
    def server_addr(self):
        return self.environ['HTTP_HOST']

    def __str__(self):
        return f'<Request(headers={self.headers}, ' \
               f'addr={self.server_addr}, ' \
               f'post_params={self.POST_params})>'
