#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko

import os
from hashlib import sha512
import logging as log
from wsgiref.simple_server import make_server
import string
from http.cookies import SimpleCookie

from app import App
from app import render_template
from config import config
from db import DB, init_db
from util import derive_token, Client, FlashManager


log.getLogger()

app = App()
init_db('storage.db')

# TODO: consider thread-safety issues for sessions global var
sessions = set()
db_manager = DB(config.get('DB_PATH'))
server_dir = config.get('SERVER_DIR')
current_users = dict()


def on_register(u_name):
    """Routine to be executed after user register"""
    os.makedirs(os.path.join(server_dir, u_name), exist_ok=True)


def is_file(u_name, server_dir_path):
    path = os.path.join(server_dir, u_name, server_dir_path.strip('/'))
    return os.path.isfile(path)


def handle_download_file(u_name, server_dir_path):
    real_path = os.path.join(server_dir, u_name, server_dir_path.strip('/'))
    return app.respond_with_file_download(real_path)


def extract_credentials_from_post_req(req):
    if req.POST_params:
        u_name = req.POST_params.get('login', [None])[0]
        u_pass = req.POST_params.get('password', [None])[0]
        if u_name and u_pass:
            u_pass_hash = sha512(u_pass.encode()).hexdigest()
            return u_name, u_pass_hash
    return None, None


def is_allowed_identifier(u_name):
    allowed = string.ascii_letters + string.digits + '_-. ()[]{}?!'
    return all([c in allowed for c in u_name])


def handle_remove(requested_path, action, client, flash_manager):
    if action == 'remove_dir':
        _handle_remove(requested_path, client, os.rmdir, flash_manager,
                       f'Directory {requested_path} was removed',
                       f'Directory {requested_path} is non-empty')

    elif action == 'remove_file':
        _handle_remove(requested_path, client, os.remove, flash_manager,
                       'File was removed successfully',
                       'Error occurred after an'
                       ' attempt to remove specified file')


def handle_upload_file(cur_client, req, f_mng):
    # print(req.file.name)
    if not is_allowed_identifier(req.file.name):
        f_mng.flash("Insufficient filename. Try to rename before upload")
        return

    new_file_path = os.path.join(
        cur_client.real_cwd(server_dir).strip('/'), req.file.name
    )
    if req.file.save_to_file(new_file_path):

        # update tree view as file structure was changed
        f_mng.flash("Uploaded file successfully", 1)
    else:
        f_mng.flash("Uploaded failed due to unhandled error")


def _handle_remove(path, client, method, flash_manager, default_msg, except_msg):
    """Common steps for both rmdir and rmfile"""
    item_path = os.path.join(server_dir, client.u_name, path.strip('/'))

    try:
        method(item_path)
    except Exception:
        flash_manager.flash(except_msg)
        return False
    else:
        flash_manager.flash(default_msg, 1)
        return True


def handle_make_dir(pseudo_dir_name, cur_client, f_mng):
    dir_name = os.path.join(cur_client.real_cwd(server_dir).strip('/'),
                            pseudo_dir_name.strip('/'))
    try:
        os.mkdir(dir_name)
    except Exception as e:
        f_mng.flash(f'No such file or directory: {pseudo_dir_name}')
        return False
    else:
        f_mng.flash(f'Created directory: {pseudo_dir_name}', 1)
        return True


@app.route('/')
def index(req):
    cookie = req.headers.get('HTTP_COOKIE')
    if cookie:
        parsed_cookie = SimpleCookie(cookie)
        session_token = parsed_cookie.get('session')

        if session_token and session_token.value in sessions:
            return app.redirect(app.url_for(req, 'main'))

    return render_template('index.html')


@app.route('/login')
def login(req):
    with FlashManager() as f_mng:
        if req.POST_params:
            u_name, u_pass_hash = extract_credentials_from_post_req(req)
            if db_manager.try_login(u_name, u_pass_hash):
                url_to_redirect = app.url_for(req, '/main')
                response = app.redirect(url_to_redirect)
                session_token = derive_token()
                sessions.add(session_token)
                response.set_cookie('session', session_token)
                current_users[session_token] = Client(u_name)
                return response

            # incorrect u_name or u_pass
            else:
                f_mng.flash('Incorrect username and/or password')
        return render_template('login.html', flash_messages=f_mng.get_flashes())


@app.route('/register')
def register(req):
    with FlashManager() as f_mng:
        if req.POST_params:
            u_name, u_pass_hash = extract_credentials_from_post_req(req)

            if not u_name or not u_pass_hash:
                f_mng.flash('Username and/or password not specified')
            elif db_manager.try_register(u_name, u_pass_hash):
                on_register(u_name)
                f_mng.flash('Registered successfully. You can now log in', 1)
            else:
                f_mng.flash('Username taken')

        return render_template('register.html', flash_messages=f_mng.get_flashes())


@app.route('/main')
def main(req):
    cookie = req.headers.get('HTTP_COOKIE')
    action = req.GET_params.get('action')

    session_token = None

    if cookie:
        parsed_cookie = SimpleCookie(cookie)
        session_token = parsed_cookie.get('session')

        if action and action == 'logout':

            # Because particular session id was removed - next condition won't
            # trigger and we wil be redirected to home in logout state,
            # previous session id cookie will not be valid
            if session_token and session_token.value in sessions:
                sessions.remove(session_token.value)

    with FlashManager() as f_mng:
        # logged-in state
        if session_token and session_token.value in sessions:
            requested_path = req.GET_params.get('path')
            create_dir_action = req.POST_params.get('dir_name_create')
            cur_client = current_users[session_token.value]

            # path wants to be deleted
            if requested_path and action:
                handle_remove(requested_path, action, cur_client, f_mng)

            # if make dir required
            elif create_dir_action:
                pseudo_dir_name = create_dir_action[0]
                handle_make_dir(pseudo_dir_name, cur_client, f_mng)

            # if upload required
            elif req.file:
                handle_upload_file(cur_client, req, f_mng)

            # if some path requested in query string and no
            # specific action requested
            elif requested_path and not action:
                # requested path - file
                if is_file(cur_client.u_name, requested_path):
                    return handle_download_file(cur_client.u_name,
                                                requested_path)
                # requested path - directory
                else:
                    cur_client.cwd = requested_path

            dir_view = cur_client.get_dir_view(server_dir)
            return render_template('main.html', dir_view=dir_view,
                                   flash_messages=f_mng.get_flashes())

    return app.redirect(app.url_for(req, '/'))


@app.err(404)
def handler_404(req=None):
    return render_template('err404.html')


if __name__ == '__main__':
    make_server(os.environ.get('HOST', ''), int(os.environ.get('PORT', 5000)), app).serve_forever()
    # make_server(config['HOST'], config['PORT'], app).serve_forever()
