FROM zhiyuanyaoj/research:latest

LABEL maintainer="Zhiyuan Yao <zhiyuan.yao@polytechnique.edu>"
ARG PROJECT=aquarius
ARG PROJECT_DIR=/opt/$PROJECT
ARG HOME=/root

WORKDIR $PROJECT_DIR

COPY build/pkglist /tmp/

RUN apt-get update && \
        apt-get install -yq --no-install-recommends \
        $(cat /tmp/pkglist) \
        && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN echo "en_US.UTF-8 UTF-8" > /etc/locale.gen && \
    locale-gen

# Configure environment
ENV SHELL=/bin/bash \
    LC_ALL=en_US.UTF-8 \
    LANG=en_US.UTF-8 \
    LANGUAGE=en_US.UTF-8

COPY build/requirements.txt /tmp/

RUN python3 -m pip install --upgrade pip; \
        python3 -m pip install --upgrade Pillow; \
        python3 -m pip install --requirement /tmp/requirements.txt; \
        rm -f /tmp/requirements.txt;

RUN set -xe  \
        && echo '#!/bin/sh' > /usr/sbin/policy-rc.d  \
        && echo 'exit 101' >> /usr/sbin/policy-rc.d  \
        && chmod +x /usr/sbin/policy-rc.d  \
        && dpkg-divert --local --rename --add /sbin/initctl  \
        && cp -a /usr/sbin/policy-rc.d /sbin/initctl  \
        && sed -i 's/^exit.*/exit 0/' /sbin/initctl  \
        && echo 'force-unsafe-io' > /etc/dpkg/dpkg.cfg.d/docker-apt-speedup  \
        && echo 'DPkg::Post-Invoke { "rm -f /var/cache/apt/archives/*.deb /var/cache/apt/archives/partial/*.deb /var/cache/apt/*.bin || true"; };' > /etc/apt/apt.conf.d/docker-clean  \
        && echo 'APT::Update::Post-Invoke { "rm -f /var/cache/apt/archives/*.deb /var/cache/apt/archives/partial/*.deb /var/cache/apt/*.bin || true"; };' >> /etc/apt/apt.conf.d/docker-clean  \
        && echo 'Dir::Cache::pkgcache ""; Dir::Cache::srcpkgcache "";' >> /etc/apt/apt.conf.d/docker-clean  \
        && echo 'Acquire::Languages "none";' > /etc/apt/apt.conf.d/docker-no-languages  \
        && echo 'Acquire::GzipIndexes "true"; Acquire::CompressionTypes::Order:: "gz";' > /etc/apt/apt.conf.d/docker-gzip-indexes  \
        && echo 'Apt::AutoRemove::SuggestsImportant "false";' > /etc/apt/apt.conf.d/docker-autoremove-suggests

RUN [ -z "$(apt-get indextargets)" ]

RUN mkdir -p /run/systemd  \
        && echo 'docker' > /run/systemd/container

# get vpp
WORKDIR $HOME
RUN git clone https://github.com/FDio/vpp.git; \
        cd vpp; \
        git checkout stable/2005; \
        apt-get update; \
        make wipe; \
        make wipe-release; \
        echo y | make install-deps; \
        echo y | make install-ext-deps;

WORKDIR $PROJECT_DIR

EXPOSE 8888

CMD ["jupyter notebook --no-browser --port=8888", "$PROJECT_DIR"]
