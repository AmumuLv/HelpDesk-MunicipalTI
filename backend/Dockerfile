# Native security backports. Keep the distribution ABI and all Debian patches.
# pyexpat below is rebuilt for this exact CPython version. Update them together.
ARG PYTHON_IMAGE=python:3.12.16-slim-trixie@sha256:4840d514c583a4d3d8cad3940e68dee6f0f6f3635c12fcd0a3d74c21a5b93a54
FROM ${PYTHON_IMAGE} AS native-security
RUN printf 'deb-src http://deb.debian.org/debian trixie main\n' > /etc/apt/sources.list.d/helpdesk-source.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates patch dpkg-dev pkg-config file automake autoconf libtool \
        libicu-dev liblzma-dev zlib1g-dev xz-utils
WORKDIR /build
ENV CFLAGS="-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3" \
    LDFLAGS="-Wl,-z,relro,-z,now"
COPY security/patches/libxml2-bounds.patch /build/xml.patch
RUN apt-get source libxml2 \
    && curl -fsSL https://download.gnome.org/sources/libxml2/2.9/libxml2-2.9.14.tar.xz -o xml-tests.tar.xz \
    && echo '60d74a257d1ccec0475e749cba2f21559e48139efba6ff28224357c7c798dfee  xml-tests.tar.xz' | sha256sum -c - \
    && mkdir /xml-tests && tar xf xml-tests.tar.xz -C /xml-tests \
    && echo '5e51f8dcadfe3294a15d9e8644d61e8d92bd5b9e72c10cf13ef010eccfbfa4df  xml.patch' | sha256sum -c - \
    && cd libxml2-*/ && patch --batch --forward --fuzz=0 -p1 < ../xml.patch && autoreconf -fi \
    && cp -rn /xml-tests/libxml2-2.9.14/test /xml-tests/libxml2-2.9.14/result . \
    && ./configure --prefix=/usr --libdir=/usr/lib --without-python --with-icu \
    && make -j2 && make check \
    && make DESTDIR=/patched install
RUN curl -fsSL https://codeload.github.com/madler/zlib/tar.gz/df84af25dc1942490e1d1c899a07619152a46148 -o zlib.tar.gz \
    && echo '03a76732cfaa124c58b67600699d935d081604385c03aa282f81a101b7536161  zlib.tar.gz' | sha256sum -c - \
    && tar xzf zlib.tar.gz && cd zlib-*/ \
    && ./configure --prefix=/usr --libdir=/usr/lib \
    && make -j2 && make check && make DESTDIR=/patched install
RUN mkdir /artifacts && cp -L /patched/usr/lib/libxml2.so.2 /artifacts/libxml2.so.2 \
    && cp -L /patched/usr/lib/libz.so.1 /artifacts/libz.so.1

# Only ffprobe is used by the API. A local-file build avoids RIST/cJSON and
# unrelated network, display and device libraries. Development keeps ffmpeg.
# Use the official upstream tag archive: ffmpeg.org was unreachable from CI.
# This is a different archive from the release .tar.xz and has its own checksum.
RUN curl -4 -fsSL --retry 2 --retry-all-errors --connect-timeout 20 --max-time 180 \
        https://codeload.github.com/FFmpeg/FFmpeg/tar.gz/refs/tags/n9.0.2 -o ffmpeg.tar.gz \
    && echo '6e374ed621e48faa40639307dff48ba6fe574a509977956d2cce9669b7cc27e9  ffmpeg.tar.gz' | sha256sum -c - \
    && tar xzf ffmpeg.tar.gz && cd FFmpeg-n9.0.2 \
    && ./configure --prefix=/probe --disable-everything --disable-autodetect --disable-network \
        --disable-doc --disable-debug --disable-x86asm --disable-ffmpeg \
        --disable-ffplay --disable-avdevice \
        --disable-avfilter --disable-swscale --enable-swresample \
        --enable-ffprobe --enable-protocol=file \
        --enable-demuxer=aac,flac,matroska,mov,mp3,ogg,wav \
        --enable-parser=aac,flac,mpegaudio,opus,vorbis \
        --enable-decoder=aac,flac,mp3,opus,vorbis,pcm_s16le,pcm_s24le,pcm_s32le,pcm_u8 \
    && make -j2 && make install
RUN mkdir /licenses \
    && cp /build/FFmpeg-n9.0.2/COPYING.LGPLv2.1 /licenses/ffmpeg-LGPL-2.1.txt \
    && cp /build/libxml2-*/Copyright /licenses/libxml2-Copyright.txt \
    && cp /build/zlib-*/README /licenses/zlib-README.txt

# Keep Debian's Expat ABI and patches, then apply the upstream security commits.
# The vendored files retain the previously verified SHA-256 values; GitHub's
# dynamic .patch rendering changed only its abbreviated blob IDs (9 to 10).
COPY security/patches/expat-empty.patch security/patches/expat-prefix.patch \
    security/patches/expat-attributes.patch /build/
RUN printf 'deb-src http://deb.debian.org/debian-security trixie-security main\n' > /etc/apt/sources.list.d/expat-security.list \
    && apt-get update && apt-get install -y --no-install-recommends cmake \
    && apt-get source expat=2.9.0-1~deb13u1 \
    && echo '96ea42cc30d4fd99ea62a7fd84d339bef7dc01135f5774b094a09274a0a54f49  expat-empty.patch' | sha256sum -c - \
    && echo '3b78184a2176ce725d21b233912033fa333466f4a5a2a17a10128002826f99fb  expat-prefix.patch' | sha256sum -c - \
    && echo '28ebac139e59e1909e50eecfd834fc4baf9dcf7dc627b4e3a81af872fd818f15  expat-attributes.patch' | sha256sum -c -
RUN cd expat-*/expat && patch --batch --forward --fuzz=0 -p2 < ../../expat-empty.patch \
    && patch --batch --forward --fuzz=0 -p2 < ../../expat-prefix.patch && patch --batch --forward --fuzz=0 -p2 < ../../expat-attributes.patch \
    && cmake -S . -B build -DCMAKE_INSTALL_PREFIX=/usr -DCMAKE_INSTALL_LIBDIR=lib \
         -DEXPAT_BUILD_DOCS=OFF -DEXPAT_BUILD_EXAMPLES=OFF -DEXPAT_BUILD_TOOLS=OFF \
         -DEXPAT_BUILD_TESTS=ON -DEXPAT_SHARED_LIBS=ON \
    && cmake --build build -j2 && ctest --test-dir build --output-on-failure \
    && DESTDIR=/patched cmake --install build \
    && cp -L /patched/usr/lib/libexpat.so.1 /artifacts/libexpat.so.1 \
    && cp COPYING /licenses/Expat-COPYING

# CPython embeds Expat in pyexpat. Rebuild the extension against the patched
# shared library as well; replacing libexpat alone would leave Python vulnerable.
RUN test "$(python -c 'import platform; print(platform.python_version())')" = 3.12.16 \
    && mkdir -p /build/cpython-expat/clinic \
    && curl -fsSL https://raw.githubusercontent.com/python/cpython/v3.12.16/Modules/pyexpat.c -o /build/cpython-expat/pyexpat.c \
    && echo 'fbde9f72de2e8eb0f8d2edcfb73276d4b4473834c1c3620908bc2e71ebec04ae  /build/cpython-expat/pyexpat.c' | sha256sum -c - \
    && curl -fsSL https://raw.githubusercontent.com/python/cpython/v3.12.16/Modules/clinic/pyexpat.c.h -o /build/cpython-expat/clinic/pyexpat.c.h \
    && echo '5e730198b2e3b644a96b411d5e594654d23146110b880a6ee9961fc919d90acb  /build/cpython-expat/clinic/pyexpat.c.h' | sha256sum -c - \
    && sed -n '/^#define XML_/p' /patched/usr/include/expat_config.h > /build/cpython-expat/expat_config.h \
    && cc -shared -fPIC -DPy_BUILD_CORE_MODULE $(python3-config --includes) \
         -I/usr/local/include/python3.12/internal -I/patched/usr/include -I/build/expat-2.9.0/expat/build \
         -L/patched/usr/lib $CFLAGS $LDFLAGS -o /artifacts/pyexpat.so /build/cpython-expat/pyexpat.c -lexpat \
    && curl -fsSL https://raw.githubusercontent.com/python/cpython/v3.12.16/LICENSE -o /licenses/CPython-LICENSE \
    && echo '3b2f81fe21d181c499c59a256c8e1968455d6689d269aa85373bfb6af41da3bf  /licenses/CPython-LICENSE' | sha256sum -c -

# development / test / production share the same image; only the CMD changes.
FROM ${PYTHON_IMAGE} AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=UTC

# WeasyPrint necesita pango/cairo; curl para el healthcheck; tini para senales.
RUN apt-get update && apt-get upgrade -y && apt-get install -y --no-install-recommends \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz-subset0 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libicu76 \
        shared-mime-info \
        fonts-liberation \
        fonts-dejavu-core \
        curl \
        tini \
        bash \
    && rm -rf /var/lib/apt/lists/*

COPY --from=native-security /artifacts/ /opt/helpdesk-native/
COPY security/install_backports.py /opt/helpdesk-native/install.py
RUN python /opt/helpdesk-native/install.py && rm -rf /opt/helpdesk-native && ldconfig
COPY --from=native-security /probe/bin/ffprobe /usr/local/bin/ffprobe
COPY --from=native-security /licenses/ /usr/local/share/helpdesk/licenses/
RUN ffprobe -version

WORKDIR /app

COPY requirements.txt constraints.txt ./
RUN python -m pip install --no-cache-dir --upgrade -c constraints.txt pip \
    && pip install --no-cache-dir -c constraints.txt -r requirements.txt

COPY . .

# Usuario no root con directorios de datos propios
RUN useradd --create-home --uid 10001 --shell /bin/bash appuser \
    && mkdir -p /data/uploads /data/exports /data/backups \
    && chown -R appuser:appuser /app /data
USER appuser

RUN python security/verify_backports.py

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=40s --retries=10 \
    CMD curl -fsS http://localhost:8000/api/health || exit 1

ENTRYPOINT ["/usr/bin/tini", "--"]

# ── develop ──────────────────────────────────────────────────
FROM base AS develop
USER root
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*
USER appuser
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir -c constraints.txt -r requirements-dev.txt
ENV APP_ENV=development PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ── prod ─────────────────────────────────────────────────────
FROM base AS prod
USER root
RUN python -m pip uninstall -y pip
USER appuser
ENV APP_ENV=production PYTHONPATH=/app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*", "--ws-max-size", "8192", "--ws-max-queue", "8"]
