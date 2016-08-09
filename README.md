# replicate-github

A tool to manage mirrors of GitHub repos.

  $ replicate-github --verbose fetch puppetlabs/puppet 'github/*'
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
  Mirror: Fetching puppetlabs/puppetlabs-modules
  127.0.0.1 - - [08/Aug/2016 14:40:21] "POST / HTTP/1.1" 200 -
  ^C
  Aborted!

### Configuration file format

This takes a configuration file, which is located at `/etc/replicate-github.yaml` by default. You may specify a different file with the `--config-file` option. The file only requires three settings:

~~~ yaml
mirror_path: "/srv/replicate-github"
github_user: "GitHub username"
github_token: "GitHub API token"
# Optional:
webhook_secret: "secret configured for webhook in GitHub"
~~~

You can generate a GitHub API token under [Settings > Personal access tokens](https://github.com/settings/tokens).
