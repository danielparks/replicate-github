# replicate-github

A tool to manage mirrors of GitHub repos.

  $ replicate-github --verbose mirror puppetlabs/puppet 'github/*'
  mirror.Collection: Fetching puppetlabs/puppet
  mirror.Collection: Fetching github/garethr-docker
  mirror.Collection: Fetching github/github-ldap
  ^C
  $ replicate-github --verbose serve
  WebhookServer: Webhook server listening on localhost:8080
  127.0.0.1 - - [10/Aug/2016 01:18:35] "POST / HTTP/1.1" 202 -
  mirror.Collection: Fetching puppetlabs/puppet
  ^C

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
