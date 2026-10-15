# Official devkitPro image, pinned to the digest used for the local baseline.
FROM devkitpro/devkitarm@sha256:116afba8df8453961de2936ffab20dd441edf4d682856c1ec8b0e53d7ed0bbf5

RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build git curl ca-certificates python3 python3-yaml \
    python3-pil pkg-config libpng-dev zlib1g-dev zip unzip \
    && rm -rf /var/lib/apt/lists/*

# Build packaging tools against this image's glibc, matching release CI.
RUN git clone --depth 1 --branch makerom-v0.19.0 \
      https://github.com/3DSGuy/Project_CTR.git /tmp/project-ctr \
    && make -C /tmp/project-ctr/makerom deps \
    && make -C /tmp/project-ctr/makerom -j4 \
    && install -m755 /tmp/project-ctr/makerom/bin/makerom /usr/local/bin/makerom \
    && rm -rf /tmp/project-ctr

RUN curl --fail --location --retry 3 \
      https://github.com/carstene1ns/3ds-bannertool/releases/download/1.2.3/bannertool-1.2.3.tar.gz \
      -o /tmp/bannertool.tar.gz \
    && mkdir /tmp/bannertool \
    && tar xzf /tmp/bannertool.tar.gz -C /tmp/bannertool --strip-components=1 \
    && cmake -S /tmp/bannertool -B /tmp/bannertool/build -DCMAKE_BUILD_TYPE=Release \
    && cmake --build /tmp/bannertool/build --parallel 4 \
    && install -m755 /tmp/bannertool/build/bannertool /usr/local/bin/bannertool \
    && rm -rf /tmp/bannertool /tmp/bannertool.tar.gz

ENV PATH="/opt/devkitpro/devkitARM/bin:${PATH}"
WORKDIR /work
