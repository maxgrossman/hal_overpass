FROM quay.io/centos/centos:stream9

ARG hal_user \
    hal_group \
    hal_uid \
    hal_gid=${hal_uid} \
    hal_shell=/bin/bash \
    hal_dir

COPY scripts/docker-entrypoint.sh /docker-entrypoint.sh
COPY scripts/docker-healthcheck.sh /docker-healthcheck.sh

COPY scripts/docker-cli-entrypoint.sh /docker-cli-entrypoint.sh

RUN dnf -y update && dnf -y install python3
RUN groupadd --non-unique --gid ${hal_gid} ${hal_group} \
 && useradd --home-dir ${hal_dir} --uid ${hal_uid} --gid ${hal_gid} -m ${hal_user}

USER ${hal_user}
WORKDIR ${hal_dir}
VOLUME ${hal_dir}
ENTRYPOINT ["/docker-entrypoint.sh"]
HEALTHCHECK CMD "/docker-healthcheck.sh"