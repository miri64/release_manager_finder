#! /usr/bin/env python3
#
# Copyright (C) 2025 TU Dresden
#
# Distributed under terms of the MIT license.

# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring

import tornado.auth
import tornado.escape
import tornado.web
import tornado

from .. import GITHUB_ORGA

__author__ = "Martine S. Lenders <martine.lenders@tu-dresden.de>"


GITHUB_TEAMS = ["maintainers", "owners"]


class GitHubOAuth2Mixin(tornado.auth.OAuth2Mixin):
    """GitHub authentication using OAuth2.

    Original code:
    https://gist.github.com/thelastpolaris/7f1395257a6f064c224f4bfdf2fa9fa4
    """

    _OAUTH_ACCESS_TOKEN_URL = "https://github.com/login/oauth/access_token?"
    _OAUTH_AUTHORIZE_URL = "https://github.com/login/oauth/authorize?"
    _OAUTH_NO_CALLBACKS = False
    _API_URL = "https://api.github.com"
    SCOPE = {}

    async def get_authenticated_user(
        self, redirect_uri, client_id, client_secret, code, extra_fields=None
    ):
        http = self.get_auth_http_client()
        args = {
            "redirect_uri": redirect_uri,
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
        }

        fields = {"login", "id"}
        if extra_fields:
            fields.update(extra_fields)
        response = await http.fetch(
            self._oauth_request_token_url(**args),
            headers={"Accept": "application/json"},
        )
        args = tornado.escape.json_decode(response.body)

        session = {
            "access_token": args.get("access_token"),
        }
        assert session["access_token"] is not None

        user = await self.github_request(
            path="/user",
            access_token=session["access_token"],
        )

        if user is None:
            return None

        fieldmap = {}
        for field in fields:
            fieldmap[field] = user.get(field)
        fieldmap["access_token"] = session["access_token"]

        return fieldmap

    async def github_request(self, path, access_token):
        url = self._API_URL + path

        response = await self.get_auth_http_client().fetch(
            url,
            headers={"Authorization": f"token {access_token}"},
            user_agent="PMR",
        )

        if response.body:
            return tornado.escape.json_decode(response.body)
        return response.code, response.reason


class GitHubTeamOAuth2Mixin(GitHubOAuth2Mixin):
    SCOPE = {"scope": ["read:org"]}

    def initialize(self, org_name, team_id):
        super().initialize()
        self.org_name = org_name
        self.team_id = team_id

    async def get_authenticated_user(
        self, redirect_uri, client_id, client_secret, code, extra_fields=None
    ):
        user = await super().get_authenticated_user(
            redirect_uri, client_id, client_secret, code, extra_fields=extra_fields
        )
        no_maintainer = True
        for team in GITHUB_TEAMS:
            try:
                await self.github_request(
                    path=f"/orgs/{GITHUB_ORGA}/teams/{team}/members/{user['login']}",
                    access_token=user["access_token"],
                )
            except tornado.httpclient.HTTPClientError:
                pass
            else:
                no_maintainer = False
        if no_maintainer:
            self.redirect(f"/not-a-maintainer?user={user['login']}")
        return user
