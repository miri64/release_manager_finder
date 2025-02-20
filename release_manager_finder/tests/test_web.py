#! /usr/bin/env python3
#
# Copyright (C) 2025 TU Dresden
#
# This file is subject to the terms and conditions of the GNU Lesser
# General Public License v2.1. See the file LICENSE in the top level
# directory for more details.

# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name

import http.cookies
import json
import os
import unittest.mock
import urllib.parse

import pytest
import tornado.httpclient
import tornado.testing
import tornado.web

os.environ["CLIENT_ID"] = "dGVzdHRlc3R0ZXN0Cg"
os.environ["CLIENT_SECRET"] = "746573747465737474657374210a"
os.environ["COOKIE_SECRET"] = "a4a8fbb3-80ac-434c-b7ac-9c897d9e75df"

from .. import web  # noqa: E402 pylint: disable=wrong-import-position

__author__ = "Martine S. Lenders <martine.lenders@tu-dresden.de>"


def test_base_handler_no_cookie(mocker):
    called = {"redirect": False}

    def redirect(self, url):
        # pylint: disable=unused-argument
        called["redirect"] = url  # pragma: no cover, should not be called!

    mocker.patch.object(web.BaseHandler, "redirect", redirect)
    mocker.patch.object(web.BaseHandler, "get_signed_cookie", lambda self, x: None)

    handler = web.BaseHandler(web.make_app([]), mocker.Mock())
    assert not handler.get_current_user()
    assert not called["redirect"]


@pytest.fixture
def teams_mock(mocker):
    yield mocker.MagicMock(
        return_value=mocker.MagicMock(
            orgs={
                web.GITHUB_ORGA: mocker.MagicMock(
                    teams={
                        "owners": mocker.MagicMock(
                            members={
                                "huey": mocker.MagicMock(
                                    get=mocker.MagicMock(return_value=(200, "x"))
                                ),
                                "dewey": mocker.MagicMock(
                                    get=mocker.MagicMock(return_value=(404, "x"))
                                ),
                            }
                        ),
                        "maintainers": mocker.MagicMock(
                            members={
                                "huey": mocker.MagicMock(
                                    get=mocker.MagicMock(return_value=(404, "x"))
                                ),
                                "dewey": mocker.MagicMock(
                                    get=mocker.MagicMock(return_value=(404, "x"))
                                ),
                            }
                        ),
                    }
                )
            },
        ),
    )


def test_base_handler_user_is_maintainer(mocker, teams_mock):
    called = {"redirect": False}

    def redirect(self, url):
        # pylint: disable=unused-argument
        called["redirect"] = url  # pragma: no cover, should not be called!

    mocker.patch.object(web.BaseHandler, "redirect", redirect)
    mocker.patch("agithub.GitHub.GitHub", teams_mock)
    mocker.patch.object(
        web.BaseHandler,
        "get_signed_cookie",
        lambda self, x: '{"access_token":"foobar","login":"huey"}',
    )

    handler = web.BaseHandler(web.make_app([]), mocker.Mock())
    user = handler.get_current_user()
    assert user["login"] == "huey"
    assert not called["redirect"]


def test_base_handler_user_is_not_maintainer(mocker, teams_mock):
    called = {"redirect": False}

    def redirect(self, url):
        # pylint: disable=unused-argument
        called["redirect"] = url

    mocker.patch.object(web.BaseHandler, "redirect", redirect)
    handler = web.BaseHandler(web.make_app([]), mocker.Mock())

    mocker.patch("agithub.GitHub.GitHub", teams_mock)

    mocker.patch.object(
        web.BaseHandler,
        "get_signed_cookie",
        lambda self, x: '{"access_token":"foobar","login":"dewey"}',
    )
    user = handler.get_current_user()
    assert user["login"] == "dewey"
    assert called["redirect"] == "not-a-maintainer?user=dewey"


def test_base_handler_data_received(mocker):
    handler = web.BaseHandler(web.make_app([]), mocker.Mock())
    assert not handler.data_received(b"test")


def test_favicon_handler_data_received(mocker):
    handler = web.FaviconHandler(web.make_app([]), mocker.Mock())
    assert not handler.data_received(b"test")


class TestBaseWebApp(tornado.testing.AsyncHTTPTestCase):
    def get_app(self):
        return web.make_app([], gh_token=os.environ.get("GITHUB_TOKEN"))

    def test_login_no_code(self):
        response = self.fetch("/login", follow_redirects=False)
        assert response.code == 302
        assert response.headers["Location"] == (
            # pylint: disable=protected-access
            web.auth.GitHubTeamOAuth2Mixin._OAUTH_AUTHORIZE_URL + "response_type=code&"
            f"redirect_uri={urllib.parse.quote('http://localhost:8888/login', safe='')}"
            f"&client_id={os.environ['CLIENT_ID']}&"
            f"scope={urllib.parse.quote('read:org')}"
        )

    @unittest.mock.patch.object(
        web.LoginHandler,
        "get_authenticated_user",
        unittest.mock.AsyncMock(
            return_value={"access_token": "foobar", "user": "huey"}
        ),
    )
    def test_login_with_code_user_allowed(self):
        response = self.fetch("/login?code=abcdefg", follow_redirects=False)

        assert response.code == 302
        assert response.headers["Location"] == "/"

        cookie = http.cookies.SimpleCookie(response.headers["Set-Cookie"])
        user = json.loads(
            tornado.web.decode_signed_value(
                os.environ["COOKIE_SECRET"], "user", cookie["user"].value
            )
        )
        assert user == {"access_token": "foobar", "user": "huey"}

    @unittest.mock.patch.object(
        web.LoginHandler,
        "get_authenticated_user",
        unittest.mock.AsyncMock(return_value=None),
    )
    def test_login_with_code_user_not_allowed(self):
        response = self.fetch("/login?code=abcdefg", follow_redirects=False)

        assert "Set-Cookie" not in response.headers
        assert response.code == 200
        assert response.body.decode() == (
            f"Unable to login. You need org:read permissions for {web.GITHUB_ORGA}"
        )

    def test_not_a_maintainer(self):
        response = self.fetch("/not-a-maintainer", follow_redirects=False)

        assert response.code == 401
        assert not response.body

    def test_not_a_maintainer_w_user(self):
        response = self.fetch("/not-a-maintainer?user=louie", follow_redirects=False)

        assert response.code == 401
        assert response.body == (
            b"401 Unauthorized: GitHub user '@louie' is not a maintainer. "
            b'<a href="/logout">Logout and go back.</a>'
        )

    @unittest.mock.patch.object(web.LogoutHandler, "clear_all_cookies")
    def test_logout(self, clear_all_cookies):
        with unittest.mock.patch.object(
            web.LogoutHandler, "current_user", {"login": "test"}
        ):
            response = self.fetch("/logout", follow_redirects=False)

        assert response.code == 302
        assert response.headers["Location"] == "/"
        clear_all_cookies.assert_called_once()

        clear_all_cookies.reset_mock()
        with unittest.mock.patch.object(web.LogoutHandler, "current_user", None):
            response = self.fetch("/logout", follow_redirects=False)

        assert response.code == 302
        assert response.headers["Location"] == "/"
        clear_all_cookies.assert_not_called()

    @unittest.mock.patch.object(web.MainHandler, "current_user", True)
    @unittest.mock.patch(
        "release_manager_finder.web.get_maintainers",
        lambda: ["huey", "dewey", "louie"],
    )
    def test_root_get_default(self):
        response = self.fetch("/")
        maintainers = web.get_maintainers()
        body = response.body.decode()
        assert f'<a href="{web.OPT_OUT_FORUM}">' in body
        assert 200 == response.code
        for maintainer in maintainers:
            assert (
                '<input class="form-check-input" name="opt-out" '
                f'type="checkbox" id="opt-out-{maintainer}" value="{maintainer}" />'
                in body
            )
            assert (
                '<input class="form-check-input" name="attendees" '
                f'type="checkbox" id="attending-{maintainer}" value="{maintainer}" />'
                in body
            )
            assert (
                '<input class="form-check-input" name="next-rm" type="checkbox" '
                f'id="next-rm-{maintainer}" value="{maintainer}" />' in body
            )

    @unittest.mock.patch.object(web.MainHandler, "current_user", True)
    @unittest.mock.patch(
        "release_manager_finder.web.get_maintainers",
        lambda: {
            "huey": 0,
            "dewey": 0,
            "louie": 0,
        },
    )
    def test_root_get_preselected_opt_out(self):
        opt_out = ["huey"]

        def initialize_mock(self, initial_opt_out_list, gh_token=None):
            # pylint: disable=unused-argument
            self.initial_opt_out_list = opt_out
            self.gh_token = gh_token

        with unittest.mock.patch.object(web.MainHandler, "initialize", initialize_mock):
            response = self.fetch("/")
        maintainers = web.get_maintainers()
        body = response.body.decode()
        assert 200 == response.code
        for maintainer in maintainers:
            if maintainer in opt_out:
                assert (
                    '<input class="form-check-input" name="opt-out" type="checkbox" '
                    f'id="opt-out-{maintainer}" value="{maintainer}" checked />' in body
                )
            else:
                assert (
                    '<input class="form-check-input" name="opt-out" type="checkbox" '
                    f'id="opt-out-{maintainer}" value="{maintainer}" />' in body
                )
            assert (
                '<input class="form-check-input" name="attendees" type="checkbox" '
                f'id="attending-{maintainer}" value="{maintainer}" />' in body
            )
            assert (
                '<input class="form-check-input" name="next-rm" type="checkbox" '
                f'id="next-rm-{maintainer}" value="{maintainer}" />' in body
            )

    @unittest.mock.patch.object(
        web.MainHandler, "current_user", {"access_token": "blafoo", "user": "louie"}
    )
    @unittest.mock.patch.object(
        web.MainHandler, "check_xsrf_cookie", unittest.mock.MagicMock()
    )
    @unittest.mock.patch(
        "release_manager_finder.web.get_maintainers",
        lambda: {
            "foobar": 0,
            "huey": 0,
            "test": 0,
            "dewey": 0,
            "louie": 0,
            "donald": 0,
        },
    )
    @unittest.mock.patch(
        "release_manager_finder.web.get_past_release_managers",
        lambda _: {
            "foobar": 1,
            "huey": 2,
            "test": 2,
            "louie": 3,
            "snafu": 5,
            "scrooge": 2,
            "donald": 2,
        },
    )
    @unittest.mock.patch(
        "random.choice",
        lambda seq: seq[0],
    )
    def test_root_post_default(self):
        response = self.fetch(
            "/",
            method="POST",
            body=urllib.parse.urlencode(
                [
                    ("next-rm", "foobar"),
                    ("opt-out", "huey"),
                    ("opt-out", "dewey"),
                    ("opt-out", "louie"),
                    ("opt-out", "dewey"),
                    ("attendees", "louie"),
                    ("attendees", "dewey"),
                    ("attendees", "foobar"),
                    ("attendees", "donald"),
                ]
            ),
        )
        body = response.body.decode()
        assert (
            """
<h1>Congratulation <a href="https://github.com/donald"><tt>@donald</tt></a> 🎉, you are the next release manager!</h1>
<p>
Here is how I came to this decision.
</p>
<h2>Selection Pool</h2>
<p>
Maintainers that are attending the VMA and not <a href="https://forum.riot-os.org/t/release-management-opt-out/3354">on the opt-out list</a> and did manage the least amount of releases managed.
The next release manager, <tt>@donald</tt>, was randomly picked from this list.
<a href="/">Increase selection.</a>
</p>
<table class="table table-responsive table-striped">
<thead>
<tr>
<th scope="col">Releases</th>
<th scope="col">Maintainer</th>
<th scope="col">Is Maintainer</th>
<th scope="col">Opt-Out</th>
<th scope="col">Attending VMA</th>
</tr>
</thead>
<tbody>

<tr class="table-success">
<td width="3em">2</td>
<td><a href="https://github.com/@donald"><tt>@donald</tt></a></td>
<td width="1em">✅</td>
<td width="1em"></td>
<td width="1em">✅</td>
</tr>

<tr class="table-success">
<td width="3em">2</td>
<td><a href="https://github.com/@foobar"><tt>@foobar</tt></a></td>
<td width="1em">✅</td>
<td width="1em"></td>
<td width="1em">✅</td>
</tr>

</tbody>
</table>

<h2>Total Release Manager Tally</h2>
<p>
Here is the list of all maintainers (<a href="">current</a> and past) who managed a release.
<span class="text-danger">Red</span> rows mark users that are either no maintainers anymore or <a href="https://forum.riot-os.org/t/release-management-opt-out/3354">opted out of release management</a>.
<span class="text-success">Green</span> rows mark maintainers who do not fall in those categories and who are attending the VMA.
Only <span class="text-success">green</span> rows are considered for the list above.
</p>
<table class="table table-responsive table-striped">
<thead>
<tr>
<th scope="col">Releases</th>
<th scope="col">User</th>
<th scope="col">Is Maintainer</th>
<th scope="col">Opt-Out</th>
<th scope="col">Attending VMA</th>
</tr>
</thead>
<tbody>

<tr class="table-danger">
<td width="3em">0</td>
<td><a href="https://github.com/@dewey"><tt>@dewey</tt></a></td>
<td width="1em">✅</td>
<td width="1em">✅</td>
<td width="1em">✅</td>
</tr>

<tr class="table-success">
<td width="3em">2</td>
<td><a href="https://github.com/@donald"><tt>@donald</tt></a></td>
<td width="1em">✅</td>
<td width="1em"></td>
<td width="1em">✅</td>
</tr>

<tr class="table-success">
<td width="3em">2</td>
<td><a href="https://github.com/@foobar"><tt>@foobar</tt></a></td>
<td width="1em">✅</td>
<td width="1em"></td>
<td width="1em">✅</td>
</tr>

<tr class="table-danger">
<td width="3em">2</td>
<td><a href="https://github.com/@huey"><tt>@huey</tt></a></td>
<td width="1em">✅</td>
<td width="1em">✅</td>
<td width="1em"></td>
</tr>

<tr class="table-danger">
<td width="3em">2</td>
<td><a href="https://github.com/@scrooge"><tt>@scrooge</tt></a></td>
<td width="1em"></td>
<td width="1em"></td>
<td width="1em"></td>
</tr>

<tr >
<td width="3em">2</td>
<td><a href="https://github.com/@test"><tt>@test</tt></a></td>
<td width="1em">✅</td>
<td width="1em"></td>
<td width="1em"></td>
</tr>

<tr class="table-danger">
<td width="3em">3</td>
<td><a href="https://github.com/@louie"><tt>@louie</tt></a></td>
<td width="1em">✅</td>
<td width="1em">✅</td>
<td width="1em">✅</td>
</tr>

<tr class="table-danger">
<td width="3em">5</td>
<td><a href="https://github.com/@snafu"><tt>@snafu</tt></a></td>
<td width="1em"></td>
<td width="1em"></td>
<td width="1em"></td>
</tr>

</tbody>
</table>

</div>"""  # noqa: E501 pylint: disable=line-too-long
            in body
        )

    @unittest.mock.patch.object(
        web.MainHandler, "current_user", {"access_token": "blafoo", "user": "louie"}
    )
    @unittest.mock.patch.object(
        web.MainHandler, "check_xsrf_cookie", unittest.mock.MagicMock()
    )
    @unittest.mock.patch(
        "release_manager_finder.web.get_maintainers",
        lambda: {
            "foobar": 0,
            "huey": 0,
            "test": 0,
            "dewey": 0,
            "louie": 0,
            "donald": 0,
        },
    )
    @unittest.mock.patch(
        "release_manager_finder.web.get_past_release_managers",
        lambda _: {
            "foobar": 1,
            "huey": 2,
            "test": 2,
            "louie": 3,
            "snafu": 5,
            "scrooge": 2,
            "donald": 2,
        },
    )
    def test_root_post_no_selection_pool(self):
        response = self.fetch(
            "/",
            method="POST",
            body=urllib.parse.urlencode(
                [
                    ("next-rm", "foobar"),
                    ("opt-out", "huey"),
                    ("opt-out", "dewey"),
                    ("opt-out", "louie"),
                    ("opt-out", "dewey"),
                    ("attendees", "louie"),
                    ("attendees", "dewey"),
                ]
            ),
        )
        body = response.body.decode()
        assert "<h2>There is no suitable candidate 😱!</h2>" in body

    def test_favicon(self):
        response = self.fetch("/favicon.svg")
        assert response.code == 200
        assert "<svg" in response.body.decode()


@pytest.mark.parametrize(
    "argv, exp",
    [
        pytest.param(
            ["command"],
            {"port": 8888, "opt-out-list": [], "token": None},
            id="defaults",
        ),
        pytest.param(
            ["command", "-o", "the-opt-out-list"],
            {
                "port": 8888,
                "opt-out-list": ["huey", "dewey", "louie"],
                "token": None,
            },
            id="w/ --opt-out-list",
        ),
        pytest.param(
            ["command", "-t", "the-token-of-all-tokens"],
            {
                "port": 8888,
                "opt-out-list": [],
                "token": "the-token-of-all-tokens",
            },
            id="w/ --gh-token",
        ),
        pytest.param(
            ["command", "-p", "12623"],
            {
                "port": 12623,
                "opt-out-list": [],
                "token": None,
            },
            id="w/ --port",
        ),
    ],
)
def test_main(mocker, argv, exp):
    mocker.patch("asyncio.Event.wait", mocker.AsyncMock())
    mocker.patch("sys.argv", argv)
    make_app = mocker.MagicMock()
    mocker.patch("release_manager_finder.web.make_app", make_app)
    mocker.patch(
        "release_manager_finder.web.get_opt_out_list",
        mocker.MagicMock(return_value=["huey", "dewey", "louie"]),
    )
    web.main()
    make_app.assert_called_once_with(exp["opt-out-list"], exp["token"])
    make_app.return_value.listen.assert_called_once_with(exp["port"])


@pytest.mark.asyncio
async def test_github_oauth2_mixin_get_authenticated_user(mocker):
    # test default
    client_mock = mocker.MagicMock(
        return_value=mocker.MagicMock(
            fetch=mocker.AsyncMock(
                return_value=mocker.MagicMock(
                    body=(
                        b'{"access_token":"foobar","login":"huey","id":12356,'
                        b'"test":"this is extra","full_name":"Tick Duck"}'
                    )
                )
            )
        )
    )
    mocker.patch.object(web.auth.GitHubOAuth2Mixin, "get_auth_http_client", client_mock)
    fieldmap = await web.auth.GitHubOAuth2Mixin().get_authenticated_user(
        "http://localhost:8888/login",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        code="0sIo65g4LzV74CWeUh8",
    )
    assert fieldmap == {"access_token": "foobar", "login": "huey", "id": 12356}

    # test for extra fields
    fieldmap = await web.auth.GitHubOAuth2Mixin().get_authenticated_user(
        "http://localhost:8888/login",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        code="0sIo65g4LzV74CWeUh8",
        extra_fields=["full_name"],
    )
    assert fieldmap == {
        "full_name": "Tick Duck",
        "access_token": "foobar",
        "login": "huey",
        "id": 12356,
    }

    # test when "/user" response is empty
    client_mock = mocker.MagicMock(
        return_value=mocker.MagicMock(
            fetch=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(
                        body=(
                            b'{"access_token":"foobar","login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    mocker.MagicMock(body=""),
                ]
            )
        )
    )
    mocker.patch.object(web.auth.GitHubOAuth2Mixin, "get_auth_http_client", client_mock)
    fieldmap = await web.auth.GitHubOAuth2Mixin().get_authenticated_user(
        "http://localhost:8888/login",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        code="0sIo65g4LzV74CWeUh8",
    )
    assert not fieldmap


@pytest.mark.asyncio
async def test_github_team_oauth2_mixin_get_authenticated_user(mocker):
    # test huey as owner
    client_mock = mocker.MagicMock(
        return_value=mocker.MagicMock(
            fetch=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(
                        body=(
                            b'{"access_token":"foobar","login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    mocker.MagicMock(
                        body=(
                            b'{"login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    mocker.MagicMock(body=b'{"huey": "Huey is an owner!"}'),
                    tornado.httpclient.HTTPClientError(401),
                ]
            )
        )
    )
    mocker.patch.object(
        web.auth.GitHubTeamOAuth2Mixin, "get_auth_http_client", client_mock
    )
    web.auth.GitHubOAuth2Mixin.initialize = mocker.MagicMock()
    mixin = web.auth.GitHubTeamOAuth2Mixin()
    mixin.initialize("RIOT-OS", "maintainers")
    fieldmap = await mixin.get_authenticated_user(
        "http://localhost:8888/login",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        code="0sIo65g4LzV74CWeUh8",
    )
    assert fieldmap == {"access_token": "foobar", "login": "huey", "id": 12356}

    # test huey as maintainer
    client_mock = mocker.MagicMock(
        return_value=mocker.MagicMock(
            fetch=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(
                        body=(
                            b'{"access_token":"foobar","login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    mocker.MagicMock(
                        body=(
                            b'{"login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    tornado.httpclient.HTTPClientError(401),
                    mocker.MagicMock(body=b'{"huey": "Huey is an maintainer!"}'),
                ]
            )
        )
    )
    mocker.patch.object(
        web.auth.GitHubTeamOAuth2Mixin, "get_auth_http_client", client_mock
    )
    web.auth.GitHubOAuth2Mixin.initialize = mocker.MagicMock()
    mixin = web.auth.GitHubTeamOAuth2Mixin()
    mixin.initialize("RIOT-OS", "maintainers")
    fieldmap = await mixin.get_authenticated_user(
        "http://localhost:8888/login",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        code="0sIo65g4LzV74CWeUh8",
    )
    assert fieldmap == {"access_token": "foobar", "login": "huey", "id": 12356}

    # test huey as neither owner nor maintainer
    called = {}

    def redirect(_, url):
        called["redirect"] = url

    client_mock = mocker.MagicMock(
        return_value=mocker.MagicMock(
            fetch=mocker.AsyncMock(
                side_effect=[
                    mocker.MagicMock(
                        body=(
                            b'{"access_token":"foobar","login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    mocker.MagicMock(
                        body=(
                            b'{"login":"huey","id":12356,'
                            b'"test":"this is extra","full_name":"Tick Duck"}'
                        )
                    ),
                    tornado.httpclient.HTTPClientError(401),
                    tornado.httpclient.HTTPClientError(401),
                ]
            )
        )
    )
    mocker.patch.object(
        web.auth.GitHubTeamOAuth2Mixin, "get_auth_http_client", client_mock
    )
    web.auth.GitHubOAuth2Mixin.initialize = mocker.MagicMock()
    web.auth.GitHubOAuth2Mixin.redirect = redirect
    mixin = web.auth.GitHubTeamOAuth2Mixin()
    mixin.initialize("RIOT-OS", "maintainers")
    fieldmap = await mixin.get_authenticated_user(
        "http://localhost:8888/login",
        client_id=os.environ["CLIENT_ID"],
        client_secret=os.environ["CLIENT_SECRET"],
        code="0sIo65g4LzV74CWeUh8",
    )
    assert not fieldmap
    assert called["redirect"] == "/not-a-maintainer?user=huey"
