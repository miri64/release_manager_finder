# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring
# pylint: disable=redefined-outer-name

import argparse
import os
import re

import agithub.GitHub
import pytest

from .. import (
    GITHUB_ORGA,
    GITHUB_REPO,
    GitHubError,
    get_team_members,
    get_owners,
    get_maintainers,
    get_past_release_managers,
    get_opt_out_list,
    filter_out_opt_out,
    sort_by_release_management,
    least_managing,
    parse_args,
    print_results,
    main,
)


@pytest.fixture
def github():
    yield agithub.GitHub.GitHub()


def test_get_team_members_success(mocker, github):
    mocked_request = mocker.patch(
        "agithub.GitHub.GitHubClient.request", return_value=(200, [{"login": "foobar"}])
    )
    team_members = get_team_members(github, "test")
    assert team_members == {"foobar": 0}
    mocked_request.assert_called_once_with(
        "GET", f"/orgs/{GITHUB_ORGA}/teams/test/members", None, {}
    )


def test_get_team_members_error(mocker, github):
    mocked_request = mocker.patch(
        "agithub.GitHub.GitHubClient.request", return_value=(400, "Error foobar")
    )
    with pytest.raises(GitHubError) as exc:
        get_team_members(github, "test")
    assert str(exc.value) == "Error foobar"
    mocked_request.assert_called_once_with(
        "GET", f"/orgs/{GITHUB_ORGA}/teams/test/members", None, {}
    )


def test_get_owners_success(mocker, github):
    mocked_request = mocker.patch(
        "agithub.GitHub.GitHubClient.request", return_value=(200, [{"login": "foobar"}])
    )
    team_members = get_owners(github)
    assert team_members == {"foobar": 0}
    mocked_request.assert_called_once_with(
        "GET", f"/orgs/{GITHUB_ORGA}/members?role=admin", None, {}
    )


def test_get_owners_error(mocker, github):
    mocked_request = mocker.patch(
        "agithub.GitHub.GitHubClient.request", return_value=(400, "Error foobar")
    )
    with pytest.raises(GitHubError) as exc:
        get_owners(github)
    assert str(exc.value) == "Error foobar"
    mocked_request.assert_called_once_with(
        "GET", f"/orgs/{GITHUB_ORGA}/members?role=admin", None, {}
    )


def test_get_maintainers(mocker, github):
    mocker.patch("release_manager_finder.get_team_members", return_value={"foobar": 0})
    mocker.patch("release_manager_finder.get_owners", return_value={"owner": 0})
    maintainers = get_maintainers(github)
    assert maintainers == {"foobar": 0, "owner": 0}

    mocker.patch(
        "release_manager_finder.get_team_members",
        return_value={"foobar": 0, "owner": 0},
    )
    maintainers = get_maintainers(github)
    assert maintainers == {"foobar": 0, "owner": 0}

    def _maintainers(_, team, *args, **kwargs):  # pylint: disable=unused-argument
        maintainers = {
            "maintainers": {"foobar": 0},
            "admin": {"snafu": 0},
        }
        return maintainers[team]

    mocker.patch("release_manager_finder.get_team_members", side_effect=_maintainers)
    maintainers = get_maintainers(github)
    assert maintainers == {"foobar": 0, "owner": 0, "snafu": 0}


def test_get_past_release_managers_success(mocker, github):
    mocked_request = mocker.patch(
        "agithub.GitHub.GitHubClient.request",
        return_value=(
            200,
            [
                {"tag_name": "2015.09", "author": {"login": "OlegHahm"}},
                {"tag_name": "2016.07", "author": {"login": "miri64"}},
                {"tag_name": "2016.10", "author": {"login": "miri64"}},
                {"tag_name": "2020.07", "author": {"login": "miri64"}},
                {"tag_name": "2020.07.1", "author": {"login": "miri64"}},
            ],
        ),
    )
    maintainers = get_past_release_managers(github)
    assert maintainers == {"kYc0o": 1, "miri64": 2, "OlegHahm": 5}
    mocked_request.assert_called_once_with(
        "GET", f"/repos/{GITHUB_ORGA}/{GITHUB_REPO}/releases", None, {}
    )


def test_get_past_release_managers_error(mocker, github):
    mocked_request = mocker.patch(
        "agithub.GitHub.GitHubClient.request", return_value=(400, "Error snafu")
    )
    with pytest.raises(GitHubError) as exc:
        get_past_release_managers(github)
    assert str(exc.value) == "Error snafu"
    mocked_request.assert_called_once_with(
        "GET", f"/repos/{GITHUB_ORGA}/{GITHUB_REPO}/releases", None, {}
    )


def test_get_opt_out_list(mocker):
    mocker.patch(
        "release_manager_finder.open",
        mocker.mock_open(read_data="huey\n   dewey\n louie  "),
    )
    opt_out_list = get_opt_out_list(argparse.Namespace(opt_out_list="test"))
    assert opt_out_list == ["huey", "dewey", "louie"]

    opt_out_list = get_opt_out_list(argparse.Namespace(opt_out_list=None))
    assert not opt_out_list


def test_filter_out_opt_out():
    maintainers = [(0, "foobar"), (0, "huey"), (0, "test"), (0, "louie")]
    opt_out_list = ["huey", "dewey", "louie"]
    maintainers = filter_out_opt_out(maintainers, opt_out_list)
    assert maintainers == [(0, "foobar"), (0, "test")]


def test_sort_by_release_management():
    maintainers = {"foobar": 3, "huey": 5, "test": 2, "louie": 0, "snafu": 2}
    assert sort_by_release_management(maintainers) == [
        (0, "louie"),
        (2, "snafu"),
        (2, "test"),
        (3, "foobar"),
        (5, "huey"),
    ]


def test_least_managing():
    current_maintainers = {"foobar", "test", "snafu"}
    maintainers = [(3, "foobar"), (5, "huey"), (2, "test"), (2, "louie"), (2, "snafu")]
    assert least_managing(maintainers, current_maintainers) == [
        (2, "test"),
        (2, "snafu"),
    ]


def test_parse_args(mocker):
    mocker.patch("sys.argv", ["command", "test_token"])
    args = parse_args()
    assert args.gh_token == "test_token"
    assert args.opt_out_list is None

    mocker.patch("sys.argv", ["command", "test_token", "test_opt_out_list"])
    args = parse_args()
    assert args.gh_token == "test_token"
    assert args.opt_out_list == "test_opt_out_list"


def test_print_results(mocker, capsys):
    mocker.patch("random.choice", lambda l: l[0])
    current_maintainers = {"foobar", "huey", "louie", "scrooge"}
    maintainers = [
        (2, "foobar"),
        (2, "huey"),
        (2, "test"),
        (3, "louie"),
        (5, "snafu"),
        (2, "scrooge"),
    ]
    opt_out_list = ["huey", "dewey", "louie"]
    print_results(maintainers, opt_out_list, current_maintainers)
    captured = capsys.readouterr()
    assert (
        captured.out
        == """Current release management tally
================================
  2	foobar
  2	test
  5	snafu
  2	scrooge


Opt-out list
============
huey
dewey
louie


Selection pool
==============
  2	foobar
  2	scrooge


The next release manager is: foobar
"""
    )


def test_main(mocker, capsys):
    mocker.patch("sys.argv", ["command", os.environ["GITHUB_TOKEN"], "mocked_file"])
    mocker.patch(
        "release_manager_finder.open",
        mocker.mock_open(read_data="miri64"),
    )
    main()
    captured = capsys.readouterr()
    in_selection_pool = False
    maintainer_comp = re.compile(r"^\s*\d+\s+(.*)\s*$")
    next_rm_comp = re.compile(r"^The next release manager is:\s+(.*)\s*$")
    expected_maintainer_pool = []
    next_rm = None
    for line in captured.out.split("\n"):
        if line == "Selection pool":
            in_selection_pool = True
        if in_selection_pool:
            match = maintainer_comp.match(line)
            if match:
                expected_maintainer_pool.append(match[1])
            else:
                match = next_rm_comp.match(line)
                if match:
                    next_rm = match[1]
    assert next_rm
    assert next_rm in expected_maintainer_pool
