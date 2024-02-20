# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Freie Universität Berlin
#
# Distributed under terms of the MIT license.

# pylint: disable=missing-class-docstring
# pylint: disable=missing-module-docstring
# pylint: disable=missing-function-docstring

import argparse
import random
import re

import agithub.GitHub

GITHUB_ORGA = "RIOT-OS"
GITHUB_REPO = "RIOT"


class GitHubError(Exception):
    pass


def get_team_members(github, team):
    status, data = github.orgs[GITHUB_ORGA].teams[team].members.get()
    if status != 200:
        raise GitHubError(data)
    return {m["login"]: 0 for m in data}


def get_owners(github):
    status, data = github.orgs[GITHUB_ORGA].members.get(role="admin")
    if status != 200:
        raise GitHubError(data)
    return {m["login"]: 0 for m in data}


def get_maintainers(github):
    maintainers = get_team_members(github, "maintainers")
    maintainers.update(get_team_members(github, "admin"))
    maintainers.update(get_owners(github))
    return maintainers


def get_past_release_managers(github):
    release_managers = {}
    status, data = github.repos[GITHUB_ORGA][GITHUB_REPO].releases.get()
    if status != 200:
        raise GitHubError(data)
    for release in data:
        if not re.match(r"^\d{4}\.\d{2}$", release["tag_name"]):
            # skip point releases and RCs
            continue
        if release["tag_name"] == "2016.07":
            # for some reason that release was authored by miri64, while kYc0o was the
            # release manager
            release_manager = "kYc0o"
        else:
            release_manager = release["author"]["login"]
        if release_manager not in release_managers:
            release_managers[release_manager] = 1
        else:
            release_managers[release_manager] += 1
    assert "OlegHahm" in release_managers
    # OlegHahm created releases 2013.08, 2014.01, 2014.05, and 2014.12, which are not
    # listed in RIOT-OS/RIOT/releases
    release_managers["OlegHahm"] += 4
    return release_managers


def get_opt_out_list(args):
    opt_out_list = []
    if args.opt_out_list:
        with open(args.opt_out_list, encoding="utf-8") as opt_out_file:
            for maintainer in opt_out_file:
                maintainer = maintainer.strip()
                if maintainer and not maintainer.startswith("#"):
                    opt_out_list.append(maintainer)
    return opt_out_list


def get_attendees_list(args):
    attendees_list = []
    with open(args.attendees_list, encoding="utf-8") as attendees_file:
        for maintainer in attendees_file:
            maintainer = maintainer.strip()
            if maintainer and not maintainer.startswith("#"):
                attendees_list.append(maintainer)
    return attendees_list


def filter_out_opt_out(maintainers, opt_out_list):
    return [m for m in maintainers if m[1] not in opt_out_list]


def filter_out_non_attendees(maintainers, attendees_list):
    return [m for m in maintainers if m[1] in attendees_list]


def sort_by_release_management(maintainers):
    maintainers_tuples = [(v, k) for k, v in maintainers.items()]
    return sorted(maintainers_tuples)


def least_managing(maintainers, current_maintainers):
    res = []
    min_managing = -1
    while len(res) <= 1:
        min_managing = min(m[0] for m in maintainers if m[0] > min_managing)
        res.extend(
            [
                m
                for m in maintainers
                if m[0] == min_managing and m[1] in current_maintainers
            ]
        )
    return res


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("gh_token", help="GitHub token (needs read:org permission)")
    parser.add_argument(
        "opt_out_list",
        help="File with list of opting out maintainers, "
        "see https://forum.riot-os.org/t/release-management-opt-out/3354 "
        "(GitHub user names, one per line)",
        default=None,
        nargs="?",
    )
    parser.add_argument(
        "attendees_list",
        help="File with list of attending maintainers",
        default=None,
    )
    return parser.parse_args()


def print_results(
    maintainers_sorted, opt_out_list, attendees_list, current_maintainers
):
    print("Current release management tally")
    print("================================")
    for maintainer in maintainers_sorted:
        print(f"{maintainer[0]:3d}\t{maintainer[1]}")
    print("\n\nOpt-out list")
    print("============")
    for maintainer in sorted(opt_out_list):
        print(f"{maintainer}")
    print("\n\nAttendees list")
    print("==============")
    for maintainer in sorted(attendees_list):
        print(f"{maintainer}")
    maintainers_sorted = filter_out_opt_out(maintainers_sorted, opt_out_list)
    maintainers_sorted = filter_out_non_attendees(maintainers_sorted, attendees_list)
    print("\n\nSelection pool")
    print("==============")
    try:
        least_managing_maintainers = least_managing(
            maintainers_sorted, current_maintainers
        )
        for maintainer in least_managing_maintainers:
            print(f"{maintainer[0]:3d}\t{maintainer[1]}")
        print(
            "\n\nThe next release manager is: "
            f"{random.choice(least_managing_maintainers)[1]}"
        )
    except ValueError:
        print("Selection pool is empty!")


def main():
    args = parse_args()
    opt_out_list = get_opt_out_list(args)
    attendees_list = get_attendees_list(args)
    github = agithub.GitHub.GitHub(token=args.gh_token, paginate=True)
    current_maintainers = get_maintainers(github)
    maintainers = current_maintainers.copy()
    past_release_managers = get_past_release_managers(github)
    maintainers.update(past_release_managers)
    maintainers_sorted = sort_by_release_management(maintainers)
    print_results(
        maintainers_sorted,
        opt_out_list,
        attendees_list,
        set(current_maintainers.keys()),
    )
