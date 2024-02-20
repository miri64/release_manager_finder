# RIOT release manager finder

Helps the RIOT community to find its next release manager

## Usage
Just clone the repo and execute 

```
./find_release_manager.py <gh-token> [<opt-out-list>] <attendees-list>
```

The GitHub token requires read:org permissions. The opt-out list shall be a file of GitHub user
names (one per line) of users [that opted out of release management][opt-out-list]. The attendees
list shall be a file of GitHub user names (one per line) of users that attend the VMA

[opt-out-list]: https://forum.riot-os.org/t/release-management-opt-out/3354
