# Philly Bike Action Administration, Bridges, and Planning
Website for [apps.bikeaction.org/](https://apps.bikeaction.org/).

## Description
Repository for the source code of the website for Philly Bike Action.
Handles membership, Stripe payments, our Discord bot and the 
postgres and Redis databases.

## Getting Started

### Prerequisites

* Docker
  * I recommend just downloading [Docker Desktop](https://www.docker.com/products/docker-desktop/).
  It downloads the docker backend and gives a 
  GUI to manage the Docker containers.
* Port 5433
     

### Executing program
```shell
# Apply migrations
make migrate
# Run server
make serve
```
Now the site should be running locally at [localhost:8000](localhost:8000)!