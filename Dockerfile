# using ubuntu LTS version
FROM ubuntu AS builder-image

# avoid stuck build due to user prompt
ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install --no-install-recommends -y python3 python3-dev python3-pip build-essential opencc wget libopencc-dev pkg-config && \
	apt-get clean && rm -rf /var/lib/apt/lists/*

COPY querytrans /build/querytrans
WORKDIR /build/querytrans

ENV RUSTUP_HOME=/usr/local/rustup \
    CARGO_HOME=/usr/local/cargo \
    PATH=/usr/local/cargo/bin:$PATH \
	PKG_CONFIG_PATH==/usr/lib/pkgconfig

RUN set -eux; \
    url="https://sh.rustup.rs"; \
    wget -O rustup-init "$url"; \
    chmod +x rustup-init; \
    ./rustup-init -y --no-modify-path --profile minimal; \
    rm rustup-init; \
    chmod -R a+w $RUSTUP_HOME $CARGO_HOME; \
    rustup --version; \
    cargo --version; \
    rustc --version; \
	cargo build --release

FROM ubuntu AS runner-image

COPY --from=builder-image /build/querytrans/target/release/libquerytrans.so /app/querytrans.so

COPY luoxu /app/luoxu
COPY requirements.txt /app
COPY ghost.jpg /app
COPY nobody.jpg /app
COPY requirements.txt .

RUN apt-get update && apt-get install -y python3 pip libpython3-dev opencc &&\
	apt-get clean && rm -rf /var/lib/apt/lists/* &&\
    pip install --no-cache-dir  -i https://mirrors.ustc.edu.cn/pypi/web/simple -r requirements.txt && pip install PySocks

# make sure all messages always reach console
ENV PYTHONUNBUFFERED=1

EXPOSE 9008

WORKDIR /app

CMD ["/usr/bin/python3","-m", "luoxu"]

