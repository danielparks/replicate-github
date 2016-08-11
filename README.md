# replicate-github

A tool to manage mirrors of GitHub repos.

  $ replicate-github --verbose mirror puppetlabs/puppet 'github/*'
  Mirror: Initializing puppetlabs/puppet
  Mirror: Fetching puppetlabs/puppet
  Mirror: Initializing github/version_sorter
  Mirror: Fetching github/version_sorter
  Mirror: Initializing github/markup
  Mirror: Fetching github/markup
  ^C
  Aborted!
  $ replicate-github --verbose serve
  serve: Serving HTTP on localhost:8080
  AsyncMirror: Starting with 2 workers
  127.0.0.1 - - [10/Aug/2016 01:18:35] "POST / HTTP/1.1" 202 -
  Mirror: Fetching puppetlabs/puppetlabs-modules
  ^C
  Aborted!

### Configuration file format

This loads configuration from `/etc/replicate-github.yaml` by default. You may specify a different file with the `--config-file` option. The file only requires three settings:

~~~ yaml
mirror_path: "/srv/replicate-github"
github_user: "GitHub username"
github_token: "GitHub API token"
~~~

There is an additional top level option, `workers`, that sets the number of
`git` subprocesses that can be run at once. It defaults to 1.

Optionally, defaults for subcommands (e.g. `serve`) may be set:

~~~ yaml
serve:
  secret: "secret configured for webhook in GitHub"
  port: 8000
~~~

You can generate a GitHub API token under [Settings > Personal access tokens](https://github.com/settings/tokens).
