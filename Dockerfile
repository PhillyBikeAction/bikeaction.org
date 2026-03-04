# ---- Lazer production build ----
FROM node:22-bookworm AS lazer-build
WORKDIR /code/
COPY ./lazer_app/projectLazer/package.json ./lazer_app/projectLazer/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install
COPY ./lazer_app/projectLazer/ ./
RUN npx ionic build --prod

# ---- Lazer dev (watch mode via docker-compose) ----
FROM node:22-bookworm AS lazer-dev
WORKDIR /code/lazer_app/projectLazer/
COPY ./lazer_app/projectLazer/package.json ./lazer_app/projectLazer/package-lock.json ./
RUN --mount=type=cache,target=/root/.npm,sharing=locked npm install
# Full source is volume-mounted at runtime; copy here so ionic build works during image build
COPY . /code/
RUN npx ionic build

# ---- Shared base: system dependencies ----
FROM ghcr.io/astral-sh/uv:python3.13-trixie AS base
RUN set -eux; \
    rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache;
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y gettext binutils libproj-dev gdal-bin
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

# ---- Development target ----
FROM base AS dev
ARG USER_ID=1000
ARG GROUP_ID=1000
ENV UV_PROJECT_ENVIRONMENT=/home/user/.venv
ENV RUFF_CACHE_DIR=/home/user/.cache/ruff
ENV PATH="${PATH}:/home/user/.local/bin"
RUN groupadd -o -g $GROUP_ID -r usergrp && \
    useradd -o -m -u $USER_ID -g $GROUP_ID user && \
    mkdir /code && chown user /code
USER user
WORKDIR /code
COPY pyproject.toml uv.lock /code/
RUN --mount=type=cache,target=/home/user/.cache/uv,uid=$USER_ID,gid=$GROUP_ID \
    uv sync --group dev --group deploy
COPY . /code/

# ---- Production target (default for Dokku) ----
FROM base AS production
WORKDIR /code
COPY pyproject.toml uv.lock /code/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --group deploy
COPY .ssh /root/.ssh
COPY . /code/
COPY --from=lazer-build /code/www /code/static/lazer
RUN \
    DJANGO_SECRET_KEY=deadbeefcafe \
    DATABASE_URL=None \
    RECAPTCHA_PRIVATE_KEY=None \
    RECAPTCHA_PUBLIC_KEY=None \
    DJANGO_SETTINGS_MODULE=pbaabp.settings \
    uv run python manage.py collectstatic --noinput
