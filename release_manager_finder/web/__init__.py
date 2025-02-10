#! /usr/bin/env python3
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

__author__ = "Martine S. Lenders <martine.lenders@tu-dresden.de>"

import argparse
import json
import os
import pathlib
import pprint
import random

import agithub
import asyncio
import tornado

from release_manager_finder import (
    GITHUB_ORGA,
    OPT_OUT_FORUM,
    get_maintainers,
    get_opt_out_list,
    get_past_release_managers,
    get_results,
)
from release_manager_finder.web import auth


CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
GITHUB_TEAM = "maintainers"
COOKIE_SECRET = os.environ["COOKIE_SECRET"]


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        cookie = self.get_signed_cookie("user")
        if cookie:
            user = json.loads(cookie)
            github = agithub.GitHub.GitHub(token=user["access_token"], paginate=True)
            status, team = github.orgs[GITHUB_ORGA].teams[GITHUB_TEAM].members[
                user["login"]
            ].get()
            if status == 404:
                self.redirect(f"not-a-maintainer?user={user['login']}")
            return user
        return cookie


class LoginHandler(BaseHandler, auth.GitHubTeamOAuth2Mixin):
    async def get(self):
        redirect_uri = self.request.full_url()
        if self.get_argument("code", False):
            user = await self.get_authenticated_user(
                redirect_uri=redirect_uri,
                client_id=CLIENT_ID,
                client_secret=CLIENT_SECRET,
                code=self.get_argument("code"),
            )
            if not user:
                self.write(
                    f"Unable to login. You need org:read permissions for {GITHUB_ORGA}"
                )
                return
            user_cookie = user
            self.set_signed_cookie("user", json.dumps(user_cookie))
            self.redirect("/")
        else:
            self.authorize_redirect(
                redirect_uri=redirect_uri,
                client_id=CLIENT_ID,
                response_type='code',
                **self.SCOPE,
            )


class NotMaintainerHandler(BaseHandler):
    def get(self):
        self.send_error(401)

    def write_error(self, status_code, **kwargs):
        user = self.get_argument("user")
        self.write(f"401 Unauthorized: GitHub user '@{user}' is not a maintainer")


class LogoutHandler(BaseHandler, auth.GitHubTeamOAuth2Mixin):
    def get(self):
        if self.current_user:
            self.clear_all_cookies()
        self.redirect("/")


class MainHandler(BaseHandler):
    def initialize(self, initial_opt_out_list: list[str], gh_token: str = None):
        self.initial_opt_out_list = initial_opt_out_list
        self.gh_token = gh_token

    @tornado.web.authenticated
    def get(self):
        maintainers = get_maintainers()
        self.render(
            "form.html",
            maintainers=maintainers,
            opt_out_forum=OPT_OUT_FORUM,
            opt_out_list=self.initial_opt_out_list,
        )

    @tornado.web.authenticated
    async def post(self):
        token = self.gh_token
        if self.current_user:
            token = self.current_user.get("access_token")
        github = agithub.GitHub.GitHub(token=token, paginate=True)

        current_maintainers = get_maintainers()
        past_release_managers = get_past_release_managers(github)
        next_release_managers = self.get_arguments("next-rm")
        opt_out_list = self.get_arguments("opt-out")
        attendees_list = self.get_arguments("attendees")
        rm_tally, least_managing_maintainers = get_results(
            current_maintainers,
            past_release_managers,
            next_release_managers,
            opt_out_list,
            attendees_list,
        )
        if least_managing_maintainers:
            next_release_manager = random.choice(least_managing_maintainers)[1]
        else:
            next_release_manager = None
        self.render(
            "release_manager.html",
            next_release_manager=next_release_manager,
            opt_out_forum=OPT_OUT_FORUM,
            selection_pool=least_managing_maintainers,
            rm_tally=rm_tally,
            current_maintainers=current_maintainers,
            opt_out=opt_out_list,
            attendees=attendees_list,
        )


class FaviconHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(
            """
<svg viewBox="0 0 192.37 192.37"><defs><style>.cls-1{fill:#bc202b;}</style></defs><path class="cls-1" d="M254.72,365.93l-22.58-42.81a9.37,9.37,0,0,1,16.26-9.29L273.82,355a11,11,0,0,1-18.73,11.56C255,366.38,254.83,366.14,254.72,365.93Z" transform="translate(-100.54 -188.15)"/><path class="cls-1" d="M226,270.91l1.2-.32.5-.14.69-.21q.76-.23,1.75-.58a58.27,58.27,0,0,0,11.24-5.42A48.66,48.66,0,0,0,255.3,251.7c4-5.6,6.42-12.41,5.11-20.32a33.05,33.05,0,0,0-1.61-6.12c-.08-.26-.2-.52-.3-.79l-.15-.39-.08-.2c.16.34-.41-.9.35.74l-.06-.12-.5-1-.25-.48-.12-.24-.09-.15c-.26-.42-.43-.79-.75-1.28s-.58-1-.9-1.39a23.44,23.44,0,0,0-9.33-8.24A23,23,0,0,0,233.71,210a33.43,33.43,0,0,0-14.11,5.54,35,35,0,0,0-10.86,11.57,29.39,29.39,0,0,0-2.95,7.21,28.28,28.28,0,0,0-.68,3.79c-.08.64-.11,1.28-.14,1.92l-.06,2.59c-.06,1.84,0,3.51,0,5.28s0,3.49,0,5.25c0,3.46.13,7.11.24,10.72l.34,10.87c.12,3.63.2,7.25.41,10.9L207,307.45l.54,10.87.14,2.71.1,3v3.28c0,1-.08,2.08-.14,3.12a60.67,60.67,0,0,1-6.72,24.74,48.79,48.79,0,0,1-7.81,10.74A46.55,46.55,0,0,1,182.72,374a49.61,49.61,0,0,1-24.26,6.49,50.23,50.23,0,0,1-23.33-5.44,43.56,43.56,0,0,1-17.29-15.81,42.43,42.43,0,0,1-2.67-5.12c-.2-.43-.37-.87-.54-1.32l-.55-1.45-.7-2c-.26-.84-.54-1.84-.79-2.75s-.39-1.72-.59-2.58-.3-1.69-.45-2.53-.24-1.68-.32-2.51a57,57,0,0,1,7.55-34.74,54.14,54.14,0,0,1,9.34-11.85,54.91,54.91,0,0,1,10.22-7.73c1.66-1,3.29-1.8,4.83-2.55.78-.35,1.54-.67,2.28-1s1.45-.6,2.15-.84c1.39-.51,2.68-1,3.88-1.28s2.28-.66,3.27-.86,1.85-.43,2.6-.57l1.89-.32,1.54-.25a9.36,9.36,0,0,1,3.2,18.45l-.55.1-1.11.2L161,296c-.54.1-1.14.27-1.84.43s-1.46.37-2.28.63-1.72.55-2.67.9a14,14,0,0,0-1.46.58l-1.53.67c-1,.52-2.11,1.05-3.2,1.73a35.66,35.66,0,0,0-12.66,12.93,37.57,37.57,0,0,0-2.39,5,42.56,42.56,0,0,0-1.72,5.59,37.59,37.59,0,0,0-.68,12.45c.06.54.12,1.07.22,1.6s.16,1.07.3,1.59.23,1.1.36,1.54l.39,1.36.72,2c0,.08-.07-.19,0,0l0,.09.07.17.14.35c.09.23.18.47.3.7a22.83,22.83,0,0,0,1.43,2.68,23.85,23.85,0,0,0,9.6,8.51,30.42,30.42,0,0,0,14.11,3.11,29.57,29.57,0,0,0,14.41-4,27.31,27.31,0,0,0,10.36-11,40.35,40.35,0,0,0,4.17-16.43l.08-2.29v-2.15l-.09-2.43-.16-2.73-.64-11-1.29-22c-.25-3.67-.36-7.37-.51-11.07l-.44-11.06c-.14-3.68-.32-7.32-.35-11.13q0-2.82-.09-5.64c0-1.86-.09-3.8,0-5.57l0-2.82c0-1.16.11-2.31.24-3.46a49.7,49.7,0,0,1,1.2-6.79,50.78,50.78,0,0,1,5-12.52,56.33,56.33,0,0,1,17.43-18.8,54.88,54.88,0,0,1,23.26-9.11,46.55,46.55,0,0,1,12.71,0,42.72,42.72,0,0,1,12.25,3.57,45.12,45.12,0,0,1,18.06,15.55c.55.76,1,1.55,1.52,2.32s1,1.68,1.46,2.52l.18.32.13.24.25.48.5,1,.06.12c.8,1.72.26.56.45,1l.12.3.24.61c.16.41.33.81.47,1.22a54.8,54.8,0,0,1,2.69,10.12,47.41,47.41,0,0,1-1,20.26,51.44,51.44,0,0,1-7.77,16.2A64.38,64.38,0,0,1,263,275.49a77.25,77.25,0,0,1-9.94,7.37,80.11,80.11,0,0,1-15.51,7.54c-1,.34-1.81.62-2.56.85l-1,.32-.94.27-1.4.37A11,11,0,0,1,225.91,271h0Z" transform="translate(-100.54 -188.15)"/></svg>"""
        )


def make_app(opt_out_list: list[str], gh_token: str = None) -> tornado.web.Application:
    return tornado.web.Application(
        [
            (
                r"/",
                MainHandler,
                {"initial_opt_out_list": opt_out_list, "gh_token": gh_token},
            ),
            (r"/favicon.svg", FaviconHandler),
            (r"/login", LoginHandler),
            (r"/logout", LogoutHandler),
            (r"/not-a-maintainer", NotMaintainerHandler),
        ],
        template_path=pathlib.Path(__file__).parent / "templates",
        autoreload=True,
        debug=True,
        cookie_secret=COOKIE_SECRET,
        login_url="/login",
        xsrf_cookies=True,
    )


async def async_main(
    port: int = 8888, opt_out_filename: str = None, gh_token: str = None
):
    if opt_out_filename:
        opt_out_list = get_opt_out_list(opt_out_filename)
    else:
        opt_out_list = []
    app = make_app(opt_out_list, gh_token)
    app.listen(port)
    await asyncio.Event().wait()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "-p",
        "--port",
        help="Port to run the web server on (default: 8888)",
        default=8888,
    )
    parser.add_argument(
        "-o",
        "--opt-out-list",
        help=f"File with list of opting out maintainers, see {OPT_OUT_FORUM} "
        "(GitHub user names, one per line)",
        default=None,
        nargs="?",
    )
    parser.add_argument(
        "-t",
        "--gh-token",
        help="GitHub token (needed to not run into rate-limiting).",
    )
    args = parser.parse_args()

    asyncio.run(async_main(args.port, args.opt_out_list, args.gh_token))
