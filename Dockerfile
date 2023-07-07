# using ubuntu LTS version
FROM ubuntu:22.04 AS builder-image

# avoid stuck build due to user prompt
ARG DEBIAN_FRONTEND=noninteractive

RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list &&\
	apt-get update && apt-get install --no-install-recommends -y python3 python3-dev python3-pip build-essential opencc wget libopencc-dev pkg-config && \
	apt-get clean && rm -rf /var/lib/apt/lists/*


COPY querytrans /build/querytrans
WORKDIR /build/querytrans

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
    RUST_VERSION=1.70.0\
	PKG_CONFIG_PATH==/usr/lib/pkgconfig

RUN set -eux; \
    dpkgArch="$(dpkg --print-architecture)"; \
    case "${dpkgArch##*-}" in \
        amd64) rustArch='x86_64-unknown-linux-gnu'; rustupSha256='0b2f6c8f85a3d02fde2efc0ced4657869d73fccfce59defb4e8d29233116e6db' ;; \
        armhf) rustArch='armv7-unknown-linux-gnueabihf'; rustupSha256='f21c44b01678c645d8fbba1e55e4180a01ac5af2d38bcbd14aa665e0d96ed69a' ;; \
        arm64) rustArch='aarch64-unknown-linux-gnu'; rustupSha256='673e336c81c65e6b16dcdede33f4cc9ed0f08bde1dbe7a935f113605292dc800' ;; \
        i386) rustArch='i686-unknown-linux-gnu'; rustupSha256='e7b0f47557c1afcd86939b118cbcf7fb95a5d1d917bdd355157b63ca00fc4333' ;; \
        *) echo >&2 "unsupported architecture: ${dpkgArch}"; exit 1 ;; \
    esac; \
    url="https://static.rust-lang.org/rustup/archive/1.26.0/${rustArch}/rustup-init"; \
    wget "$url"; \
    echo "${rustupSha256} *rustup-init" | sha256sum -c -; \
    chmod +x rustup-init; \
    ./rustup-init -y --no-modify-path --profile minimal --default-toolchain $RUST_VERSION --default-host ${rustArch}; \
    rm rustup-init; \
    chmod -R a+w $RUSTUP_HOME $CARGO_HOME; \
    rustup --version; \
    cargo --version; \
    rustc --version; \
	cargo build --release


FROM ubuntu:22.04 AS runner-image

COPY --from=builder-image /build/querytrans/target/release/libquerytrans.so /app/querytrans.so


COPY luoxu /app/luoxu
COPY requirements.txt /app
COPY querytrans.so /app
COPY ghost.jpg /app
COPY nobody.jpg /app
COPY requirements.txt .

RUN sed -i 's@//.*archive.ubuntu.com@//mirrors.ustc.edu.cn@g' /etc/apt/sources.list &&\
    apt-get update && apt-get install -y python3.11 pip libpython3.11-dev opencc &&\
	apt-get clean && rm -rf /var/lib/apt/lists/* &&\
    pip install --no-cache-dir  -i https://mirrors.ustc.edu.cn/pypi/web/simple -r requirements.txt

# make sure all messages always reach console
ENV PYTHONUNBUFFERED=1

EXPOSE 9008

WORKDIR /app

CMD ["/usr/bin/python3","-m", "luoxu"]

