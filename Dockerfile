FROM python:3.12-slim AS base

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    pkg-config \
    sudo \
    passwd \
    xvfb \
    xauth \
    libgl1 \
    libgles2 \
    libegl1 \
    libopengl0 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libxcb1 \
    libevdev-dev \
    libinih-dev \
    libpam0g-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace

RUN ln -sf /usr/local/bin/python3 /usr/bin/python3

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install --upgrade pip \
    && python -m pip install pytest meson ninja

# Default test image intentionally skips mediapipe for faster, more reliable runs.
FROM base AS test
RUN grep -v '^mediapipe==' /tmp/requirements.txt > /tmp/requirements-test.txt \
    && python -m pip install -r /tmp/requirements-test.txt

COPY docker/entrypoint-pytest.sh /usr/local/bin/entrypoint-pytest.sh
RUN chmod +x /usr/local/bin/entrypoint-pytest.sh

ENTRYPOINT ["/usr/local/bin/entrypoint-pytest.sh"]
CMD ["tests", "-v", "-m", "not mediapipe_integration", "-o", "cache_dir=/tmp/pytest_cache"]

# Optional image for PAM smoke tests; includes full requirements.
FROM base AS pam-smoke
RUN python -m pip install -r /tmp/requirements.txt

COPY docker/entrypoint-pam-sudo-smoke.sh /usr/local/bin/entrypoint-pam-sudo-smoke.sh
RUN chmod +x /usr/local/bin/entrypoint-pam-sudo-smoke.sh

ENTRYPOINT ["/usr/local/bin/entrypoint-pam-sudo-smoke.sh"]

