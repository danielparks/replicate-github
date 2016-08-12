replicate-github
================

replicate-github sets up and maintains mirrors of GitHub organizations and
individual repos. It can serve webhook endpoints and keep the mirrors updated
continuously, or it can be run ad hoc from the command line.

::

    $ replicate-github --verbose mirror puppetlabs/puppet 'github/*'
    mirror.Collection: Fetching puppetlabs/puppet
    mirror.Collection: Fetching github/garethr-docker
    mirror.Collection: Fetching github/github-ldap
    ^C
    $ replicate-github --verbose serve --update-org github
    WebhookServer: Webhook server listening on localhost:8080
    127.0.0.1 - - [10/Aug/2016 01:18:35] "POST / HTTP/1.1" 202 -
    mirror.Collection: Fetching puppetlabs/puppet
    ^C

Webhook
~~~~~~~

The webhook server accepts POST to any URL (the path is ignored). A shared
secret should be set so that events can't be sent from non-GitHub sources.

By default the webhook server ensures that mirrors are updated at least once a
day if no events are received. See ``replicate-github serve --help`` for more
information.

GitHub webhook configuration
----------------------------

Create the webhook with any URL under the one served by the application. Set
the secret to a random string, and put it in ``replicate-github.yaml`` like so:

.. code:: yaml

    serve:
      secret: "secret configured for webhook in GitHub"

Select the "Repository" and "Push" events to send.

Security
--------

If a secret is configured then any event not containing the correct secret will
be rejected.

Only two parts of the payload are used: the full name of the repo, and the
deleted flag. The full name of the repo is validated to ensure it contains no
special characters (like / or .).

This will create or update a mirror for any repo name as long as the secret is
correct. That means if you configure the webhook for a repo that hasn't already
been mirrored it will start mirroring the repo as soon as an event comes in.

Configuration file
~~~~~~~~~~~~~~~~~~

Configuration is loaded from the value of ``--config-file``, which defaults to
``/etc/replicate-github.yaml``. The file requires three settings:

.. code:: yaml

    mirror_path: "/srv/replicate-github"
    github_user: "GitHub username"
    github_token: "GitHub API token"

You can generate a GitHub API token under `Settings > Personal access
tokens <https://github.com/settings/tokens>`_.

There is an additional top level option, ``workers``, that sets the number of
``git`` subprocesses that can be run at once. It defaults to 1.

Optionally, defaults for subcommands (e.g. ``serve``) may be set:

.. code:: yaml

    serve:
      secret: "secret configured for webhook in GitHub"
      port: 8000
      update_org:
        - github
        - puppetlabs

Note that parameter names in the configuration file use "_" instead of "-". For
example, the parameter ``--update-org`` is called ``update_org`` in the
configuration file.
