# Native security backports. Keep the distribution ABI and all Debian patches.
FROM python:3.12-slim-trixie AS native-security
RUN printf 'deb-src http://deb.debian.org/debian trixie main\n' > /etc/apt/sources.list.d/helpdesk-source.list \
    && apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates patch dpkg-dev pkg-config file automake autoconf libtool \
        libicu-dev liblzma-dev zlib1g-dev xz-utils
WORKDIR /build
ENV CFLAGS="-O2 -fstack-protector-strong -D_FORTIFY_SOURCE=3" \
    LDFLAGS="-Wl,-z,relro,-z,now"
RUN apt-get source libxml2 \
    && curl -fsSL https://download.gnome.org/sources/libxml2/2.9/libxml2-2.9.14.tar.xz -o xml-tests.tar.xz \
    && echo '60d74a257d1ccec0475e749cba2f21559e48139efba6ff28224357c7c798dfee  xml-tests.tar.xz' | sha256sum -c - \
    && mkdir /xml-tests && tar xf xml-tests.tar.xz -C /xml-tests \
    && curl -fsSL https://github.com/GNOME/libxml2/commit/d1686f91dbda141a752200419d35639fd6b38340.patch -o xml.patch \
    && echo '5e51f8dcadfe3294a15d9e8644d61e8d92bd5b9e72c10cf13ef010eccfbfa4df  xml.patch' | sha256sum -c - \
    && cd libxml2-*/ && patch -p1 < ../xml.patch && autoreconf -fi \
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
RUN curl -fsSL https://ffmpeg.org/releases/ffmpeg-9.0.2.tar.xz -o ffmpeg.tar.xz \
    && echo '8c3850283eb25fa026482078a04051e0be17347b09ef81a0849bec15a96e002e  ffmpeg.tar.xz' | sha256sum -c - \
    && tar xf ffmpeg.tar.xz && cd ffmpeg-9.0.2 \
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
    && cp /build/ffmpeg-9.0.2/COPYING.LGPLv2.1 /licenses/ffmpeg-LGPL-2.1.txt \
    && cp /build/libxml2-*/Copyright /licenses/libxml2-Copyright.txt \
    && cp /build/zlib-*/README /licenses/zlib-README.txt

# development / test / production share the same image; only the CMD changes.
FROM python:3.12-slim-trixie AS base

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
