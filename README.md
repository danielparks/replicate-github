# replicate-github

replicate-github sets up and maintains mirrors of GitHub organizations and
individual repos. It can serve webhook endpoints and keep the mirrors updated
continuously, or it can be run ad hoc from the command line.

  $ replicate-github --verbose mirror puppetlabs/puppet 'github/*'
  mirror.Collection: Fetching puppetlabs/puppet
  mirror.Collection: Fetching github/garethr-docker
  mirror.Collection: Fetching github/github-ldap
  ^C
  $ replicate-github --verbose serve --org github
  WebhookServer: Webhook server listening on localhost:8080
  127.0.0.1 - - [10/Aug/2016 01:18:35] "POST / HTTP/1.1" 202 -
  mirror.Collection: Fetching puppetlabs/puppet
  ^C

### Configuration file format

Configuration is loaded from the value of `--config-file`, which defaults to
`/etc/replicate-github.yaml`. The file requires three settings:

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

You can generate a GitHub API token under [Settings > Personal access
tokens](https://github.com/settings/tokens).
