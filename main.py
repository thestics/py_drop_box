#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko

import os
import logging as log
from wsgiref.simple_server import make_server

from app import App
from app import render_template
from config import config
from views import AppData, ViewsManager


log.getLogger()

app = App()
app_data = AppData(app, config)
view_manager = ViewsManager(app_data)
view_manager.register_all_views()


@app.err(404)
def handler_404(req=None):
    return render_template('err404.html')


if __name__ == '__main__':
    make_server(os.environ.get('HOST', ''), int(os.environ.get('PORT', 5000)), app).serve_forever()
    # make_server(config['HOST'], config['PORT'], app).serve_forever()
