FROM node:22-bookworm AS build-lazer

ARG GIT_REV
ENV GIT_REV=${GIT_REV}

WORKDIR /code/

COPY ./lazer_app/projectLazer/package.json /code/
COPY ./lazer_app/projectLazer/package-lock.json /code/
RUN --mount=type=cache,target=/root/.npm,sharing=locked \
    npm install

COPY ./lazer_app/projectLazer/ /code/

RUN npx ionic build --prod


FROM python:3.13-bullseye

RUN set -eux; \
    rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' > /etc/apt/apt.conf.d/keep-cache;
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update \
    && apt-get install -y gettext binutils libproj-dev gdal-bin libgl1

ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1
RUN mkdir /code
WORKDIR /code
COPY requirements /code/requirements
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/base.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements/deploy.txt
RUN python -c "from ultralytics import YOLO; YOLO('yolov8s.pt')"

COPY .ssh /root/.ssh
COPY . /code/

COPY --from=build-lazer /code/www /code/static/lazer

RUN \
    DJANGO_SECRET_KEY=deadbeefcafe \
    DATABASE_URL=None \
    RECAPTCHA_PRIVATE_KEY=None \
    RECAPTCHA_PUBLIC_KEY=None \
    DJANGO_SETTINGS_MODULE=pbaabp.settings \
    python manage.py collectstatic --noinput
