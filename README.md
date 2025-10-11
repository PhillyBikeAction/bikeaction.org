# apps.bikeaction.org

This Django codebase is what powers [apps.bikeaction.org](https://apps.bikeaction.org)

Aside from the Django web site, it also hosts our [discord bot](/pba_discord/bot.py)
which is built with [interactions.py](https://interactions-py.github.io/interactions.py/).


## Getting Started

First you'll want to ensure that you have created a
[fork](https://github.com/PhillyBikeAction/apps/fork)
of this repo in your own GitHub account.
This will allow you to push your changes to GitHub so that they can be shared with the main
repository via Pull Request.

### Dependencies

The local development environment is built with
[Docker/Docker Compose](https://www.docker.com/products/docker-desktop/)
and orchestrated with [make](https://www.gnu.org/software/make/).

### Cloning the repo

Clone you fork of the repo:

```shell
git clone https://github.com/<your github username>/apps.git
```

### Windows Specific Instruction

1. [Install WSL](https://learn.microsoft.com/en-us/windows/wsl/install#prerequisites) on windows.
We'll use Ubuntu here, but you may use any other distro.
2. Install "make":
    ```shell
    sudo apt-get install make
    ```
3. Open this project in VS Code and open a new WSL terminal in VS Code.
This opens WSL in the directory where your repo is.
Now run this command to start the service:
    ```shell
    make serve
    ```

If you do not want to use VScode, you may also open WSL and run this command to get WSL to access
your repo directory in the windows filesystem

```shell
cd /mnt/<path to repo in windows>
```

If you are getting a `python\r’: No such file or directory` error, run:

```shell
git config core.autocrlf false
git rm --cached -r .
git reset --hard
```

If you see any error messages about your database after attempting to run `make serve`,
run the following command to get your database setup correctly
```shell
make migrate
```

### Starting the services

```shell
make serve
```

This command should do everything necessary to get the service up and running locally.
After it completes, you can open a browser to [http://localhost:8000/](http://localhost:8000)
to view the running web app.

You can login as `admin@example.com` with password `password`.
This user has full permissions across all parts of the app.

### Suspending the services

If you want to stop the app to save resources locally

```shell
make stop
```

Will shut down the containers.

For a more complete "get rid of it all!" or to reset a broken environment:

```
make clean
```

Will completely destroy your local containers.

## Deployment

Deployments to [apps.bikeaction.org](https://apps.bikeaction.org) occur on merge to `main` branch.

You can watch the progress of the deploy to our [dokku](https://dokku.com) instance
in the GitHub Actions output.
