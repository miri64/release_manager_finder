# RIOT release manager finder

**The tests are currently broken.**

Helps the RIOT community to find its next release manager

## Usage
Just clone the repo ,install dependencies

```bash
pip install -r requirements.txt
```

and execute

```bash
./find_release_manager.py -t <gh-token> [<opt-out-list>] <attendees-list>
```

The GitHub token requires read:org permissions. The opt-out list shall be a file of GitHub user
names (one per line) of users [that opted out of release management][opt-out-list]. The attendees
list shall be a file of GitHub user names (one per line) of users that attend the VMA

## Usage of the Web App
Install dependencies

```bash
pip install -r requirements.txt -r requirements-web.txt
```

Configure [an OAuth app](https://github.com/settings/developers) with `http://example.org/login`
as "authorization callback URL" (replace `example.org` with your server, default `localhost:8888`).

Execute

```bash
COOKIE_SECRET="<some long and random string>" \
    CLIENT_ID="<your OAuth App's client ID>" \
    CLIENT_SECRET="<your OAuth App's client secret>" \
    ./web.py [-o <opt-out-list>]
```

The opt-out list shall be formatted as above but is purely optional and only used to prefill the
form of the web app.


### Run in docker

```
docker build -t release-manager-finder .
docker run \
    -e COOKIE_SECRET="<som long and random string>" \
    -e CLIENT_ID="<your OAuth App's client ID>" \
    -e CLIENT_SECRET="<your OAuth App's client secret>" \
    -d -p 8888:8888 \
    -v ${PWD}:/app/ \   # optional
    release-manager-finder:latest
```

(though it is probably better to use [`--env-file`][docker-env] for the environment variables instead)

[opt-out-list]: https://forum.riot-os.org/t/release-management-opt-out/3354
[docker-env]: https://docs.docker.com/reference/cli/docker/container/run/#env
