#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko


import jinja2


TEMPLATE_ENV = jinja2.Environment(
            loader=jinja2.FileSystemLoader('./templates/'),
            autoescape=jinja2.select_autoescape(['html', 'xml'])
        )
