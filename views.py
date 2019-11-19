#!/usr/bin/env python3
# -*-encoding: utf-8-*-
# Author: Danil Kovalenko

import os
from http.cookies import SimpleCookie
from hashlib import sha512
import string

from util import FlashManager, Client, derive_token
from app import render_template
from db import DB, init_db


class AppData:

    def __init__(self, app, conf):
        self.app = app
        self.conf = conf
        self.db_path = conf.get('DB_PATH')
        self.db_manager = DB(self.db_path)
        self.server_dir = self.conf.get('SERVER_DIR')

        # TODO: consider thread-safety issues for next global variables
        self.sessions = set()
        self.current_users = dict()
        init_db(self.db_path)


class ViewsManager:

    route = None
    route_classes = {}

    def __init__(self, app_data):
        self.app_data = app_data

    def register_all_views(self):
        for route, route_cls in self.route_classes.items():
            self.app_data.app.route(route)(route_cls(self.app_data))

    def __init_subclass__(cls):
        ViewsManager.route_classes[cls.route] = cls

    def __call__(self, req):
        raise NotImplementedError

    def extract_credentials_from_post_req(self, req):
        if req.POST_params:
            u_name = req.POST_params.get('login', [None])[0]
            u_pass = req.POST_params.get('password', [None])[0]
            if u_name and u_pass:
                u_pass_hash = sha512(u_pass.encode()).hexdigest()
                return u_name, u_pass_hash
        return None, None

    def is_allowed_identifier(self, u_name):
        allowed = string.ascii_letters + string.digits + '_-. ()[]{}?!'
        return all([c in allowed for c in u_name])


class IndexView(ViewsManager):

    route = '/'

    def __call__(self, req):
        cookie = req.headers.get('HTTP_COOKIE')
        if cookie:
            parsed_cookie = SimpleCookie(cookie)
            session_token = parsed_cookie.get('session')

            if session_token and session_token.value in self.app_data.sessions:
                return self.app_data.app.redirect(
                    self.app_data.app.url_for(req, 'main')
                )

        return render_template('index.html')


class LoginView(ViewsManager):

    route = '/login'

    def __call__(self, req):
        with FlashManager() as f_mng:

            if req.POST_params:
                u_name, u_pass_hash = self.extract_credentials_from_post_req(req)

                if self.app_data.db_manager.try_login(u_name, u_pass_hash):
                    url_to_redirect = self.app_data.app.url_for(req, '/main')
                    response = self.app_data.app.redirect(url_to_redirect)
                    session_token = derive_token()
                    self.app_data.sessions.add(session_token)
                    response.set_cookie('session', session_token)
                    client = Client(u_name, self.app_data.server_dir)
                    self.app_data.current_users[session_token] = client
                    return response

                # incorrect u_name or u_pass
                else:
                    f_mng.flash('Incorrect username and/or password')
            return render_template('login.html',
                                   flash_messages=f_mng.get_flashes())


class RegisterView(ViewsManager):

    route = '/register'

    def on_register(self, u_name):
        """Routine to be executed after user register"""
        os.makedirs(os.path.join(self.app_data.server_dir, u_name),
                    exist_ok=True)

    def __call__(self, req):
        with FlashManager() as f_mng:
            if req.POST_params:
                u_name, u_pass_hash = self.extract_credentials_from_post_req(req)

                if not u_name or not u_pass_hash:
                    f_mng.flash('Username and/or password not specified')
                elif self.app_data.db_manager.try_register(u_name, u_pass_hash):
                    self.on_register(u_name)
                    f_mng.flash('Registered successfully. You can now log in',
                                1)
                else:
                    f_mng.flash('Username taken')

            return render_template('register.html',
                                   flash_messages=f_mng.get_flashes())


class MainView(ViewsManager):

    route = '/main'

    def handle_upload_file(self, cur_client, req, f_mng):
        # print(req.file.name)

        if not self.is_allowed_identifier(req.file.name):
            f_mng.flash("Insufficient filename. Try to rename before upload")
            return

        new_file_path = os.path.join(
            cur_client.real_cwd().strip('/'), req.file.name
        )
        if req.file.save_to_file(new_file_path):

            # update tree view as file structure was changed
            f_mng.flash("Uploaded file successfully", 1)
        else:
            f_mng.flash("Uploaded failed due to unhandled error")

    def handle_remove(self, requested_path, action, client, flash_manager):
        if action == 'remove_dir':
            self._handle_file_system_action(
                requested_path, client, os.rmdir, flash_manager,
                f'Directory {requested_path} was removed',
                f'Directory {requested_path} is non-empty'
            )

        elif action == 'remove_file':
            self._handle_file_system_action(
                requested_path, client, os.remove, flash_manager,
                'File was removed successfully',
                'Error occurred after an'
                ' attempt to remove specified file'
            )

    def handle_make_dir(self, pseudo_dir_name, client, f_mng):
        dir_name = os.path.join(client.real_cwd().strip('/'),
                                pseudo_dir_name.strip('/'))

        self._handle_file_system_action(
            dir_name, client, os.mkdir, f_mng,
            f"No such file or directory: {pseudo_dir_name}",
            f'Created directory: {pseudo_dir_name}')

    def _handle_file_system_action(self, path, client: Client, method,
                                   flash_manager, default_msg, except_msg):
        """Common steps for mkdir rmdir and rmfile"""
        item_path = os.path.join(self.app_data.server_dir,
                                 client.u_name,
                                 path.strip('/'))

        try:
            method(item_path)
        except Exception:
            flash_manager.flash(except_msg)
            return False
        else:
            flash_manager.flash(default_msg, 1)
            return True

    def is_file(self, u_name, server_dir_path):
        path = os.path.join(self.app_data.server_dir, u_name,
                            server_dir_path.strip('/'))
        return os.path.isfile(path)

    def handle_download_file(self, u_name, server_dir_path):
        real_path = os.path.join(self.app_data.server_dir,
                                 u_name,
                                 server_dir_path.strip('/'))
        return self.app_data.app.respond_with_file_download(real_path)

    def __call__(self, req):
        cookie = req.headers.get('HTTP_COOKIE')
        action = req.GET_params.get('action')

        session_token = None

        if cookie:
            parsed_cookie = SimpleCookie(cookie)
            session_token = parsed_cookie.get('session')

            if action and action == 'logout':
                # Because particular session id was removed - next
                # condition won't trigger and we wil be redirected to
                # home in logout state, previous session id cookie will
                # not be valid
                if session_token and session_token.value in self.app_data.sessions:
                    self.app_data.sessions.remove(session_token.value)

        with FlashManager() as f_mng:
            # logged-in state
            if session_token and session_token.value in self.app_data.sessions:
                requested_path = req.GET_params.get('path')
                create_dir_action = req.POST_params.get('dir_name_create')
                cur_client = self.app_data.current_users[session_token.value]

                # path wants to be deleted
                if requested_path and action:
                    self.handle_remove(requested_path, action,
                                       cur_client, f_mng)

                # if make dir required
                elif create_dir_action:
                    pseudo_dir_name = create_dir_action[0]
                    self.handle_make_dir(pseudo_dir_name, cur_client, f_mng)

                # if upload required
                elif req.file:
                    self.handle_upload_file(cur_client, req, f_mng)

                # if some path requested in query string and no
                # specific action requested
                elif requested_path and not action:
                    # requested path - file
                    if self.is_file(cur_client.u_name, requested_path):
                        return self.handle_download_file(cur_client.u_name,
                                                         requested_path)
                    # requested path - directory
                    else:
                        cur_client.cwd = requested_path

                dir_view = cur_client.get_dir_view()
                return render_template('main.html', dir_view=dir_view,
                                       flash_messages=f_mng.get_flashes())

        return self.app_data.app.redirect(self.app_data.app.url_for(req, '/'))