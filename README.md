# Philly Bike Action Administration, Bridges, and Planning

## Getting Started

First you'll want to ensure that you have created a
[fork](https://github.com/PhillyBikeAction/abp/fork)
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
git clone https://github.com/<your github username>/abp.git
```

### Windows Specific Instruction

We will be using WSL for this. Experimentation to get the Makefile to run natively on windows
failed. In part because the Makefile runs unix only shell commands such as `id -u`

First you will need to install WSL on windows. If you do not have that already microsoft has 
handy page to walk you through it [link](https://learn.microsoft.com/en-us/windows/wsl/install#prerequisites).
We will be using Ubuntu for this installation process but you may use any distro

The only dependency that you will need to install is make. Run this command in WSL to install it
```shell
sudo apt-get install make
```

Great you now you should be ready to start this service. There is two common ways to do this.
The first is to open this project in VScode and open a new wsl terminal in VScode. This should open 
WSL in the directory where your repo is. From there just run
```shell
make serve
```

If you do not want to use VScode you may also open WSL and run this command to get WSL to access 
your repo directory in the windows filesystem
```shell
cd /mnt/<path to abp repo in window>
```

Now to address some potential problems that might not be universal

If you are getting a `python\r’: No such file or directory` error. This is the windows
new line `\n\r` causing problems when a unix new line `\n` is expected. To correct this 
there are several methods but one is to use git to replace all the `\n\r` in the project
with `\n` this can be done by running these three commands in your command line

```shell
git config core.auto crlf false
git rm --cached -r
git reset --hard
```

Lastly if you run into any error messages about your database after attempting to run `make serve`
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
