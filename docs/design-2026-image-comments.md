# PageDrop 设计方案:图片资产 · 评论协作 · About Us

> 状态:**待评审 (Draft)** · 作者:cc · 日期:2026-07-08
> 本文覆盖三块**要实施**的能力,外加一节**未来 roadmap**(Workspace 级零知识模式,不承诺时间)。

## 背景与定位

PageDrop 现状:多用户、版本不可变的 Markdown/HTML 发布平台,面向**人和 Agent 双受众**。已有 CLI + 全局 Skill,可见性为 public/unlisted/private(访问控制,非加密)。

本次三个方向,都服务同一个核心工作流:

> 电脑端 Agent 通过 skill 自动把关键内容 `publish` 成不可变 URL → 用户在任意设备上阅读、**划评论/提修订** → Agent 通过 CLI 拉取未解决评论 → 修改、发新版本、`resolve` 评论 → 迭代闭环。

系统只做**轻量的文档与协作数据存储 + 结构化接口**,不内置重的 Agent 逻辑;Agent 的循环放在 CLI/skill 侧。图片是这个闭环里的一等公民(人机都要能存、能取、能内嵌)。

---

# Part A · 图片资产(图床)

## A.1 目标 & 用户故事

- 用户/Agent 在 Markdown/HTML 里内嵌图片,发布后图片跨设备可见(类比 Overleaf 内嵌图)。
- Agent `pull` 一篇文档时,能连同附件图片一起拿到本地,从而"看到"图片内容。
- 移动端 web 能上传图片。
- 图片的可访问性**继承所属 project 的可见性**:private 项目的图,匿名/他人一律拿不到。

## A.2 数据模型 `Asset`

图片**不塞进正文**,作为独立资产存储,正文只保存引用。

```
assets
  id            uuid  pk
  workspace_id  uuid  fk -> workspaces  (index)
  project_id    uuid  fk -> projects    (index, nullable: 允许 workspace 级共享资产)
  sha256        char(64)  (index)        -- 内容寻址,去重
  content_type  varchar(100)             -- image/png, image/jpeg, image/webp, ...
  byte_size     integer
  width         integer  nullable         -- 图片元数据,可选
  height        integer  nullable
  storage_key   varchar(400)             -- 存储后端里的 key(相对路径 / S3 key)
  original_name varchar(300) nullable
  created_by_user_id  uuid nullable
  created_by_token_id uuid nullable
  created_by_source   varchar(20)         -- web|cli|api|agent
  created_at    timestamptz
  UNIQUE (workspace_id, sha256)           -- 同 workspace 内按内容去重
```

**去重**:上传时先算 sha256,命中已有则直接复用记录,不重复落盘。

## A.3 存储层抽象(关键:先本地,后可换)

定义一个 `StorageBackend` 接口,当前只实现本地磁盘:

```python
class StorageBackend(Protocol):
    def put(self, key: str, data: bytes, content_type: str) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...
```

- **LocalDiskBackend**(现在):落到挂载卷,`key = {workspace_id}/{sha256[:2]}/{sha256}`。docker-compose 加一个 `assets_data` 卷,`ASSETS_DIR=/data/assets`。
- **S3Backend**(以后):同接口换实现,配置 `ASSETS_BACKEND=s3` + bucket/endpoint 即可,业务代码零改动。

> 单机 Compose 阶段**不引入对象存储**,避免过度设计。抽象留好,迁移时只加一个类。

## A.4 上传限制

- 允许类型白名单:`image/png|jpeg|webp|gif|svg+xml`(svg 需过 sanitize,防 XSS)。
- 单文件上限(建议 10 MB,配置项 `ASSET_MAX_BYTES`)。
- 上传计入 secret-scan 无关(二进制),但记 audit log。

## A.5 API 接口

| Method | Path | Auth | 说明 |
| --- | --- | --- | --- |
| POST | `/assets` | cookie(editor+)或 token(`assets:write`) | multipart 上传;body 带 `workspace_slug`,可选 `project_slug`。返回 `{id, sha256, content_type, byte_size, url}` |
| GET | `/assets/{id}` | 继承 project 可见性 | 返回二进制(带正确 Content-Type、`Cache-Control: immutable`) |
| GET | `/public/assets/{id}` | 无鉴权,仅 public/unlisted 项目的资产 | 供公开页/分享链接内嵌 |

**访问控制**:`GET /assets/{id}` 走和正文一致的可见性判断——
- 资产挂在 private 项目 → 匿名 404、非成员 403;
- public/unlisted 项目 → 可经 `/public/assets/{id}` 读;
- 分享链接页内的图,由 share token 会话授权读取。

## A.6 引用与渲染

正文里统一用**稳定引用 scheme**,与最终域名解耦:

```markdown
![架构图](pagedrop://asset/8f3a...c1)
```

- **渲染时**(服务端 markdown→html 或前端):把 `pagedrop://asset/<id>` 改写成实际 URL——公开页改写成 `/public/assets/<id>`,登录态页面改写成 `/api/v1/assets/<id>`。
- 好处:换域名、换存储后端、改可见性都不动正文;引用天然可被 Agent 解析(拿到 id 就能下载)。
- 兼容:也允许正文直接写外链图片(`https://...`),系统不代管。

## A.7 CLI 集成(发布 & 拉取的双向改写)

**发布 `pagedrop publish`**:
1. 扫描待发布正文里的**本地图片路径**(`![](./img/x.png)`、绝对路径等)。
2. 对每个本地图:算 sha256 → `POST /assets`(命中去重则跳过上传)→ 拿到 asset id。
3. 把正文里的本地路径**改写成 `pagedrop://asset/<id>`**,再提交版本。
4. 外链图片(http/https)保持不动。

**拉取 `pagedrop pull <ws>/<slug>`**(新命令):
1. 取指定版本正文。
2. 解析其中所有 `pagedrop://asset/<id>`,逐个 `GET /assets/<id>` 下载到本地 `./assets/<id>.<ext>`。
3. 把正文里的引用改写成本地相对路径,写出 `.md`/`.html`。
4. 这样 Agent 就"拿到了带图的完整文档",能读图内容、据此修订。

## A.8 前端(web)

- `NewPageView` / 编辑器:粘贴或选择图片 → 调 `POST /assets` → 自动插入 `pagedrop://asset/<id>` 引用。移动端走同一上传接口(input capture)。
- `PageRenderer`:渲染前把 `pagedrop://asset/<id>` 解析成可读 URL(按当前是登录态还是公开态选择端点)。

## A.9 迁移

新增 alembic `0003_assets`,建 `assets` 表。无存量数据风险。

---

# Part B · 评论协作 + CLI 取评论

## B.1 目标 & 用户故事

把 PageDrop 从"发布工具"升级为"人机协作文档":用户在任意设备上对某篇文档划评论,Agent 通过 CLI 拉取未解决评论并迭代。**系统只存评论 + 给结构化接口**,不内置 Agent 循环。

## B.2 设计取舍:评论 project 级,锚定用"文本引用"

- 评论**归属于 project**(不是绑死某个 version),这样 Agent 发新版本后旧评论仍在、仍可 resolve,契合"迭代"语义。
- 每条评论**记录它是针对哪个 version 创建的**(`version_number`),供上下文与"漂移"判断。
- **锚定策略**:采用业界成熟的 **TextQuoteSelector**(Hypothesis / AnnotatorJS 同款)——存 `quote`(选中文本)+ `prefix`/`suffix`(前后各若干字符)。渲染时在正文里模糊定位;定位不到则标记为 `orphaned`(孤立),仍在列表可见。
  - 为什么不用字符 offset:offset 在正文一改就全废;quote+前后缀在小改动下仍能重定位,且**对 Agent 极友好**——Agent 直接拿到 `quote` 文本就知道评论指向哪段,无需渲染。

## B.3 数据模型 `Comment`

```
comments
  id            uuid  pk
  project_id    uuid  fk -> projects (index)
  thread_root_id uuid nullable        -- null=顶层评论;非空=某线程的回复
  anchor_version_number  integer      -- 针对哪个版本创建
  anchor_quote  text    nullable       -- 选中文本(顶层评论必填,回复可空)
  anchor_prefix varchar(200) nullable
  anchor_suffix varchar(200) nullable
  body          text                   -- 评论正文(markdown)
  status        varchar(20)            -- open | resolved   (仅顶层有意义)
  author_user_id  uuid nullable
  author_token_id uuid nullable
  author_source   varchar(20)          -- web|cli|api|agent
  author_display  varchar(120)         -- 冗余显示名(人 / "agent:cc")
  created_at    timestamptz
  resolved_at   timestamptz nullable
  resolved_by_* ...
```

线程模型:顶层评论 `thread_root_id = null`;回复挂 `thread_root_id = 顶层id`。`resolve` 作用在顶层,整条线程视为已解决。

## B.4 API 接口

| Method | Path | Auth | 说明 |
| --- | --- | --- | --- |
| GET | `/projects/{ws}/{slug}/comments?status=open` | cookie(member)或 token(`comments:read`) | 列出评论(含线程),按 status 过滤 |
| POST | `/projects/{ws}/{slug}/comments` | 同上 + `comments:write` | 新建顶层评论或回复(`thread_root_id`) |
| POST | `/comments/{id}/resolve` | member 或 `comments:write` | 标记 resolved |
| POST | `/comments/{id}/reopen` | 同上 | 重新打开 |
| DELETE | `/comments/{id}` | 作者本人或 admin+ | 删除 |

新增 scope:`comments:read`、`comments:write`(加进 `VALID_SCOPES` / `FULL_SCOPES`)。

## B.5 CLI 命令(Agent 闭环的关键)

```
pagedrop comments list <ws>/<slug> [--status open] [--json]
    列出评论。--json 输出结构化数组,含 quote / body / thread,供 Agent 消费。

pagedrop comments reply <comment_id> "已按建议修改,见 v3"
pagedrop comments resolve <comment_id>
pagedrop comments reopen <comment_id>
```

**Agent 典型迭代循环**(放在 skill/CLI 侧,系统不管):
1. `pagedrop comments list justin/report --status open --json`
2. 对每条:读 `quote` + `body` → 修改本地文档
3. `pagedrop publish`(发新版本,顺带上传新图)
4. 逐条 `pagedrop comments reply ...` + `resolve ...`

## B.6 前端(web)

- `PageRenderer` 旁挂一个**评论侧栏**:选中正文文本 → "添加评论" → 存 quote+prefix/suffix。
- 已有评论在正文中高亮 quote;点击定位。
- 顶层评论可回复、可 resolve;resolved 折叠。
- 移动端:长按选择文本添加评论(与桌面同一接口)。

## B.7 权限

- 谁能评论:workspace member(cookie)或带 `comments:write` 的 token。
- private 项目的评论只有成员/授权 token 可见,和正文一致。
- 分享链接页是否允许评论 → **未决问题**(见文末),初版建议**只读不可评论**。

## B.8 迁移

新增 alembic `0004_comments`,建 `comments` 表。

---

# Part C · About Us 页

## C.1 目标

一个静态展示页,讲清 PageDrop 是什么、给谁用、隐私立场。它是**隐私承诺的落地位置**——未来上零知识模式时,承诺写在这里才有说服力。

## C.2 内容结构

- 一句话定位:为人与 Agent 打造的、版本不可变的发布与协作平台。
- 核心能力:版本不可变 / 多端可读 / 密码与过期分享 / Agent 友好(CLI + 结构化 API)/ 图文内嵌 / 评论协作。
- 隐私立场:
  - 现状:三档可见性(public/unlisted/private),private 仅 workspace 成员可见。
  - 诚实说明:private 是**访问控制**,平台运维方在数据库层面技术上可读——**不夸大**。
  - 指向 roadmap:计划提供 **Workspace 级零知识加密**,届时连平台方都无法读取(见 Part D)。
- 联系/开源信息(GitHub 链接)。

## C.3 实现

- 新增 `apps/web-vue/src/views/AboutView.vue`,路由 `/about`,`NavBar` 加入口。
- 纯静态,无后端;文案走 i18n 友好的结构(即使暂不做多语言,也别硬编码散落)。

---

# Part D · 未来 Roadmap:Workspace 级零知识模式(不承诺时间)

> **定位:潜在方向,按使用者需求再决定是否做。** 放在这里是为了让前面三块的设计不与它冲突。

## D.1 为什么放在 Workspace 层级

把零知识**绑定到 workspace**而非单篇 project,是个更干净的模型:
- 一个"私密 workspace"整体启用加密,里面所有 project 都是零知识 → 用户心智是"这是我的保险箱空间"。
- 避免同一 workspace 里加密/非加密项目混杂带来的 UI 与密钥管理复杂度。
- workspace 成员共享该 workspace 的密钥(密钥分发用成员公钥包裹)。

## D.2 机制(草案)

- 加密/解密全在**客户端**(浏览器 + CLI)。服务器只存密文。
- workspace 有一个对称主密钥;分享 = 分享密钥,放 URL `#fragment`(不发往服务器,Cryptpad/MEGA 同款)。
- CLI 密钥存 `~/.pagedrop`;publish 前加密、pull 后解密。
- 图片同样客户端加密后再上传(Part A 的 asset 存密文)。
- 评论同样客户端加密,锚定改用**不透明 block id**(因服务端拿不到明文,无法做 quote 定位)。

## D.3 取舍(必须让用户知情)

加密 workspace 里**丧失**:服务端渲染、全文搜索/索引、公开分享给无 key 的人、密码找回(忘了 key = 数据永久丢失)。性能上多一层加解密(对文档体量可忽略)。

## D.4 结论

技术可行(libsodium / age),但是一个**独立产品模式**,不是加个开关。是否做取决于是否有用户真的愿意为"零知识"放弃这些便利。**本轮不实现,仅在 About Us 里作为承诺方向提及。**

---

# 实施顺序与里程碑

| 阶段 | 内容 | 依赖 |
| --- | --- | --- |
| 1 | **图片资产**:Asset 模型 + 本地存储 + 上传/读取 API + `pagedrop://asset` 渲染改写 + CLI publish 改写 | 无 |
| 2 | **CLI pull**:拉取正文 + 下载附件图 → 本地可编辑 | 阶段 1 |
| 3 | **评论**:Comment 模型 + API + scope + CLI `comments` 子命令 | 无(可与 1 并行) |
| 4 | **前端**:web 图片上传 UI + 评论侧栏 | 阶段 1、3 |
| 5 | **About Us** 页 | 无 |
| — | (future) Workspace 零知识模式 | 视需求 |

# 未决问题(请评审时定夺)

1. 分享链接页是否允许**匿名评论**?初版建议只读。
2. 图片单文件上限 / workspace 总容量配额?建议单文件 10 MB,配额暂不做。
3. SVG 上传是否开放(需 sanitize)?建议初版**先不收 SVG**,只收位图。
4. 评论作者显示名:Agent 评论如何标识(`agent:cc`?token 名?)。
5. asset 是否允许 project 间共享(`project_id` nullable),还是强制绑定单 project?
