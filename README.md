功能说明
====

落絮可以 CJK 友善的方式索引 Telegram 群组与频道，并提供 API 供前端使用。

安装与配置
====

配置 luoxu
----

* 安装依赖请见 `requirements.txt` 文件
* [获取](https://core.telegram.org/api/obtaining_api_id)一份 Telegram API key
* 复制 `config.toml.example` 并按需要修改
* 如果你想要索引私有群组/频道，请使用 `telethon` 加载会话并获取其 id

设置数据库
----

* 安装 PostgreSQL 及 pgroonga
* 使用 `createdb` 命令创建数据库
* 使用 `postgre` 用户身份连接到该数据库，并执行 `CREATE EXTENSION pgroonga;`
* 导入 `dbsetup.sql` 脚本，如 `psql DBNAME < dbsetup.sql`

配置 Web 前端
----

* 可使用 [luoxu-web](https://github.com/lilydjwg/luoxu-web)
* 修改 `src/App.svelte` 中的 API URL
* 运行 `npm run build` 编译文件
* 使用 Web 服务器 serve `public` 目录

你也可以使用 Vercel 来方便快捷地部署此项目。

当然了，你也可以自己另外编写 Web 页面来使用此 API。

注意事项
====

不要直接将索引了私有群组/频道的 API 公开于网络上！任何人都能获取其内容的。公开索引了公开群组或频道的服务前，也请获取群组/频道管理员的同意。

luoxu 相当于运行一个 Telegram 客户端，其权限是完全的（包括创建新的登录、结束已有会话、设置两步验证等）。请注意保护账号安全，不要在不信任的服务器上登录与运行本项目！

请注意配置数据库权限。Arch Linux 上默认安装的 PostgreSQL 很可能是对本地用户不设防的（请查阅 `/var/lib/postgres/data/pg_hba.conf` 配置文件）。

使用
====

搜索消息时，搜索字符串不区分简繁（会使用 OpenCC 自动转换），也不进行分词（请手动将可能不连在一起的词语以空格分开）。

搜索字符串支持以下功能：

* 以空格分开的多个搜索词是「与」的关系
* 使用 `OR`（全大写）来表达「或」条件
* 使用 `-` 来表达排除，如 `落絮 - 测试`
* 使用小括号来分组
