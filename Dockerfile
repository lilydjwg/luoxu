# 第一步：构建阶段
FROM rustlang/rust:nightly as builder

# 安装依赖库
RUN apt-get update && \
    apt-get install -y cmake libopencc-dev

# 设置工作目录
WORKDIR /app

# 复制源代码到构建容器
COPY querytrans /app/querytrans
COPY luoxu-cutwords /app/luoxu-cutwords

# 编译 querytrans 库
WORKDIR /app/querytrans
RUN cargo build --release

# 编译词云插件（可选）
WORKDIR /app/luoxu-cutwords
RUN cargo build --release

# 第二步：运行阶段
FROM python:3.11-slim

# 安装运行所需的依赖项
RUN apt-get update && \
    apt-get install -y libopencc1.1 postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 复制 Python 依赖项文件
COPY requirements.txt /app/

# 安装 Python 依赖项
RUN pip install --no-cache-dir -r requirements.txt

# 从构建阶段复制编译后的文件
COPY --from=builder /app/querytrans/target/release/libquerytrans.so /app/querytrans.so
COPY --from=builder /app/luoxu-cutwords/target/release/luoxu-cutwords /usr/local/bin/

# 复制项目的其余文件
COPY . /app

# 暴露应用端口
EXPOSE 8000

# 设置默认命令来运行 Luoxu
CMD ["python", "-m", "luoxu"]
