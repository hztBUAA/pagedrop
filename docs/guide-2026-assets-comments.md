# PageDrop 图床 + 评论协作:实现原理导读

> 面向「我(维护者)想搞懂这块怎么实现、有哪些可学习的设计」的技术导读。
> 覆盖:图床(Asset)、`pagedrop://asset/<id>` 引用方案、CLI 带图发布闭环、评论协作(Agent-ready)、安全鉴权,以及 Codex Review 结论与已知限制。

---

## 0. 一分钟结论(先回答你的疑惑)

- **图床在哪?** 在我们自己的服务器上。当前是**本地磁盘**(`assets_dir`,Docker volume 持久化);存储层做了抽象接口,以后换 S3/R2 只改配置、不改业务代码。
- **每张图有唯一 URL 吗?** 有。每个 asset 有唯一 id,可通过 `/api/v1/assets/<id>`(鉴权)或 `/api/v1/public/assets/<id>`(公开)取到原图——这就是「图床」的感觉。
- **但内容里存的不是真实 URL**,而是稳定的间接引用 `pagedrop://asset/<id>`。渲染时前端/客户端再解析成真实 URL。这是本设计最关键的一招(见 §2.4)。
- **Agent 用 CLI 发带图文档方便吗?** 很方便:`pagedrop publish notes.md ...` 会自动扫描 Markdown/HTML 里的**本地图片**,上传成 asset,并把引用改写成 `pagedrop://asset/<id>`,然后才发布。反向有 `pagedrop pull` 把图片拉回本地。
- **Markdown 和 HTML 都能引用吗?** 都能。Markdown `![](pagedrop://asset/<id>)`、HTML `<img src="pagedrop://asset/<id>">` 都支持(HTML 需让 sanitizer 放行该 scheme,已修复,见 §6)。
- **评论闭环?** Agent 可通过 CLI 查历史版本、拉评论、按 `open/resolved` 筛选、回复、解决/重开——闭环已打通(见 §4)。

---

## 1. 数据模型:content-addressed 的 Asset

`backend/app/models/asset.py`:

```python
ALLOWED_IMAGE_TYPES = {
    "image/png": "png", "image/jpeg": "jpg",
    "image/webp": "webp", "image/gif": "gif",
}

class Asset(UUIDMixin, Base):
    __tablename__ = "assets"
    __table_args__ = (
        UniqueConstraint("workspace_id", "sha256", name="uq_workspace_asset_sha256"),
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("workspaces.id"), index=True)
    # 可空:资产通常绑定到 project,但也可能是 workspace 级(草稿期)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID, ForeignKey("projects.id"), index=True)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    content_type: Mapped[str] = mapped_column(String(100))
    byte_size: Mapped[int] = mapped_column(Integer)
    storage_key: Mapped[str] = mapped_column(String(400))   # 磁盘/对象存储里的 key
    original_name: Mapped[str | None] = mapped_column(String(300))
    created_by_source: Mapped[str] = mapped_column(String(20), default="web")  # web | agent
    # ... created_by_user_id / token_id / created_at
```

**可学习点:**

1. **内容寻址(content-addressed)**:去重键是 `(workspace_id, sha256)`。同一 workspace 里相同字节的图片只存一份——天然去重,省存储。
2. **元数据与字节分离**:数据库存元数据(尺寸、类型、归属),真实字节存在存储后端。DB 行很小,查询快。
3. **归属分两层**:`workspace_id`(必填,鉴权边界)+ `project_id`(可空,决定公开可见性)。草稿期图片可以先「无主」(project 还没创建),发布时再认领(§3.3)。

---

## 2. 图床的四个关键部件

### 2.1 存储层抽象:今天本地盘,明天 S3

`backend/app/services/storage.py`:

```python
class StorageBackend(Protocol):
    def put(self, key: str, data: bytes) -> None: ...
    def get(self, key: str) -> bytes: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...

class LocalDiskBackend:
    def __init__(self, root: str): self.root = Path(root)
    def _path(self, key: str) -> Path:
        # key 由服务端生成(workspace/hash 前缀/hash),绝非用户输入
        return self.root / key
    def put(self, key, data): 
        p = self._path(key); p.parent.mkdir(parents=True, exist_ok=True); p.write_bytes(data)
    def get(self, key): return self._path(key).read_bytes()
```

**可学习点:** 用 `typing.Protocol` 定义接口,业务只依赖接口。以后写一个 `S3Backend` 实现同样四个方法,在 `get_backend()` 里按配置切换即可,**上传/下载/发布代码一行都不用动**。这就是「面向接口编程 + 依赖倒置」的落地。

`storage_key` 的布局(在 `asset_service._storage_key`):

```python
def _storage_key(workspace_id, sha256):
    return f"{workspace_id.hex}/{sha256[:2]}/{sha256}"
```

按 workspace 分目录、再用 hash 前两位分桶——避免单目录塞几十万文件导致的文件系统性能问题(和 git 的 `.git/objects` 同款思路)。

### 2.2 上传服务:校验 → 去重 → 落盘

`backend/app/services/asset_service.py`(节选,含并发竞态处理):

```python
def create_asset(db, *, workspace_id, project_id, data, content_type, ...):
    if content_type not in ALLOWED_IMAGE_TYPES:
        raise UnsupportedAssetTypeError(content_type)     # → 415
    if len(data) > max_bytes:
        raise AssetTooLargeError(len(data))               # → 413

    sha256 = hashlib.sha256(data).hexdigest()
    existing = db.scalar(select(Asset).where(
        Asset.workspace_id == workspace_id, Asset.sha256 == sha256))
    if existing is not None:
        return existing                                   # 去重命中,直接复用

    key = _storage_key(workspace_id, sha256)
    storage.get_backend().put(key, data)
    asset = Asset(workspace_id=workspace_id, project_id=project_id, sha256=sha256, ...)
    db.add(asset)
    try:
        db.commit()
    except IntegrityError:
        # 并发上传同一份字节,输给了唯一约束;回退到对方已插入的那一行
        db.rollback()
        return db.scalar(select(Asset).where(
            Asset.workspace_id == workspace_id, Asset.sha256 == sha256))
    db.refresh(asset)
    return asset
```

**可学习点:** 「先查后插」在并发下有竞态(两个请求都查不到 → 都插入 → 一个撞唯一约束 500)。正确姿势是**乐观处理**:让唯一约束兜底,`IntegrityError` 时回退查对方插入的行。这是 upsert 类逻辑的通用模式。

### 2.3 上传端点与鉴权

`backend/app/api/v1/assets.py`:`POST /assets` 是 `multipart/form-data`(`file` + `workspace_slug` + 可选 `project_slug`)。授权规则:

```python
def _authorize_upload(db, actor, workspace, project_slug):
    if actor.token is not None:                    # API token(Agent)
        actor.require_scope("assets:write")
        if actor.token.workspace_id != workspace.id: raise 403
        if project_slug and not actor.token_allows_project(project_slug): raise 403
        return
    if actor.user and actor.user.is_platform_admin: return
    role = perms.get_role(db, actor.user_id, workspace.id)
    if not perms.role_at_least(role, ROLE_EDITOR): raise 403   # 网页用户需 editor+
```

返回体带 `ref`:

```python
return AssetCreateResponse(**AssetOut.model_validate(asset).model_dump(),
                           ref=asset_ref(asset.id))   # pagedrop://asset/<id>
```

### 2.4 引用方案:为什么不直接存真实 URL?

`backend/app/core/urls.py`:

```python
def asset_ref(asset_id) -> str:
    """稳定、与存储位置无关的引用,内嵌进正文。"""
    return f"pagedrop://asset/{asset_id}"
```

内容(Markdown/HTML)里存的是 `pagedrop://asset/<id>`,**不是** `https://.../assets/<id>`。好处:

- **位置无关(location independence)**:以后域名变了、从本地盘迁到 S3、CDN 前缀变了,历史文档**一个字都不用改**——因为它们存的是逻辑引用,不是物理 URL。
- **鉴权自适应**:同一个 ref,在**登录后台**渲染时解析成 `/assets/<id>`(走鉴权,能看私有图);在**公开页**渲染时解析成 `/public/assets/<id>`(只服务公开 project 的图)。同一份内容,两种上下文,自动选对 URL。

前端解析(`apps/web-vue/src/components/PageRenderer.vue`):

```ts
const ASSET_REF = /pagedrop:\/\/asset\/([0-9a-fA-F-]{8,})/g;
function resolveAssets(text) {
  return text?.replace(ASSET_REF, (_m, id) => assetUrl(id, props.publicView ?? false));
}
// 发送给渲染 iframe 前,把 sourceContent / renderedHtml 里的 ref 全部替换
```

`assetUrl`(`apps/web-vue/src/api/client.ts`):

```ts
export function assetUrl(assetId, publicView) {
  const path = publicView ? `/public/assets/${assetId}` : `/assets/${assetId}`;
  return `${window.location.origin}${BASE}${path}`;
}
```

### 2.5 「唯一 URL」= 图床感 + 两条服务通道

- `GET /api/v1/assets/<id>`:鉴权通道。可见性**跟随所属 project**;workspace 级(无主)资产要 workspace 成员才可读;API token 还要过 scope + 项目白名单(§6 修复点)。
- `GET /api/v1/public/assets/<id>`:公开通道。只服务「属于可见 project」的资产,`project_id` 为空的草稿图一律 404:

```python
@router.get("/public/assets/{asset_id}")
def public_asset(asset_id, user=Depends(get_optional_user), db=...):
    asset = asset_service.get_asset(db, asset_id)
    if asset is None or asset.project_id is None:
        raise HTTPException(404, "not_found")           # 无主草稿图不公开
    project = db.get(Project, asset.project_id)
    if project is None or not perms.can_view_project(db, user, project):
        raise HTTPException(404, "not_found")           # 可见性跟随 project
    return Response(content=asset_service.read_bytes(asset),
                    media_type=asset.content_type,
                    headers={"Cache-Control": "public, max-age=31536000, immutable"})
```

**可学习点:** 内容寻址的资产是不可变的,可以放心 `immutable` 长缓存——URL 变了内容一定变,永不缓存失效。

---

## 3. Agent 用 CLI 发布带图文档的完整闭环

### 3.1 扫描正文里的本地图片

`apps/cli/src/media.ts`:

```ts
const MD_IMAGE   = /!\[[^\]]*\]\(\s*([^)\s]+)(?:\s+"[^"]*")?\s*\)/g;   // ![alt](path)
const HTML_IMAGE = /<img\b[^>]*?\bsrc\s*=\s*["']([^"']+)["']/gi;        // <img src="path">

export function isLocalPath(p) {
  // http(s):/data:/pagedrop:/协议相对/锚点/mailto: 都不算本地
  return !/^(https?:|data:|pagedrop:|\/\/|#|mailto:)/i.test(p);
}
export function extractLocalImageRefs(content) { /* 用上面两个正则收集本地路径 */ }
```

### 3.2 发布时:上传 + 改写引用

`apps/cli/src/index.ts`(`uploadLocalImages` + `publish`):

```ts
async function uploadLocalImages(client, content, baseDir, workspace, slug) {
  let out = content, count = 0;
  for (const ref of extractLocalImageRefs(content)) {
    const abs = resolve(baseDir, ref);
    if (!existsSync(abs)) { warn(`image not found, left as-is: ${ref}`); continue; }
    const form = new FormData();
    form.append("file", new Blob([readFileSync(abs)], { type: mimeForPath(ref) }), basename(ref));
    form.append("workspace_slug", workspace);
    form.append("project_slug", slug);
    const asset = await client.postForm("/assets", form);
    out = replaceRef(out, ref, asset.ref);       // 本地路径 → pagedrop://asset/<id>
    count += 1;
  }
  return { content: out, count };
}
```

调用方式:

```bash
pagedrop publish notes.md -w my-ws -s release-notes -m "v1.2"
# 自动上传 notes.md 里引用的本地图片,改写引用,再发布
# --no-images 可关闭;从 stdin 读时不扫描(没有 baseDir)
```

**便利性评价:** 对 Agent 很友好——它只需生成「带本地图片路径的 Markdown」,`publish` 一步搞定上传 + 改写 + 发布,不用先单独调上传 API 再拼 URL。去重让重复图片零成本。

### 3.3 关键补丁:发布时「认领」草稿图

网页新建页面时,图片可能在 project 还不存在时就上传了(`project_id` 为空)。这种无主图**公开页取不到**(§2.5 会 404)。所以发布时要把正文引用到的、本 workspace 的无主图挂到该 project 上:

`backend/app/services/asset_service.py`:

```python
def link_referenced_assets(db, *, workspace_id, project_id, content) -> int:
    ids = {uuid.UUID(m) for m in _ASSET_REF.findall(content)}   # 抠出 pagedrop://asset/<id>
    if not ids: return 0
    assets = db.scalars(select(Asset).where(
        Asset.id.in_(ids),
        Asset.workspace_id == workspace_id,
        Asset.project_id.is_(None),          # 只认领「无主」的,不抢别的 project 的图
    )).all()
    for a in assets: a.project_id = project_id
    return len(assets)
```

在 `project_service.publish()` 提交前调用。**可学习点:** 这是「先上传、后归属」这类延迟绑定流程里的典型收尾操作——把游离资源在合适时机挂到正式实体上。

### 3.4 反向:拉回本地

`pagedrop pull -w my-ws -s release-notes -o ./out` 会把版本正文拉下来,把 `pagedrop://asset/<id>` 引用对应的图下载到 `./out/assets/<id>.<ext>`,并把引用改写成本地相对路径——Agent 可离线编辑后再 `publish` 回去。

---

## 4. 评论协作(Agent-ready)

### 4.1 数据模型:挂在 project,而非某个版本

`backend/app/models/comment.py`(要点):`Comment` 有 `project_id`(而非 version_id,**评论跨版本存活**)、`thread_root_id`(可空,回复指向根评论)、锚点三件套 `anchor_quote/prefix/suffix` + `anchor_version_number`(TextQuoteSelector,定位到「当时引用的那段文字」)、`status`(open/resolved)、`author_source`(web/agent)、`author_display`。

**可学习点:** 评论锚定用「引用文字 + 前后文」而非「第几行/第几个字符」——文档改了行号会变,但引用的文字通常还在,定位更鲁棒(Hypothesis/Medium 的做法)。

### 4.2 列表过滤:回复永远随线程返回

`backend/app/services/comment_service.py`:

```python
def list_comments(db, project_id, *, status=None):
    stmt = select(Comment).where(Comment.project_id == project_id)
    if status is not None:
        roots = select(Comment.id).where(
            Comment.project_id == project_id,
            Comment.thread_root_id.is_(None),
            Comment.status == status)
        # 命中状态的根评论 + 它们的全部回复(回复本身没有 status)
        stmt = stmt.where((Comment.thread_root_id.in_(roots)) | (Comment.id.in_(roots)))
    return list(db.scalars(stmt.order_by(Comment.created_at.asc())))
```

**可学习点:** `status` 只加在根评论上,回复不单独筛——按 `open` 过滤时,把匹配根评论的回复也带出来,客户端才能看到完整对话,而不是断头的回复。

### 4.3 作者展示:一眼看出是不是 Agent

```python
def _author_display(actor):
    if actor.token is not None:  return f"agent:{actor.token.name}"
    if actor.user is not None:   return actor.user.name or actor.user.email
```

### 4.4 CLI 闭环命令

```bash
# 看历史版本
pagedrop versions -w my-ws -s doc
# 拉评论,只看未解决的,机器可读
pagedrop comments list -w my-ws -s doc --status open --json
# 回复某条线程
pagedrop comments reply <comment_id> "已在 v3 修复" -w my-ws -s doc
# 解决 / 重开
pagedrop comments resolve <comment_id>
pagedrop comments reopen  <comment_id>
```

这正是你要的闭环:Agent 发布 → 人评论 → Agent 拉 `--status open` → 回复 + 迭代发布新版本 → `resolve`。

### 4.5 权限:user vs token 的差异

- 读评论:token 需 `comments:read`;user 需 project 可见。
- 写/解决/重开:token 需 `comments:write` + 过项目白名单;user 需 **workspace 成员**(任意角色)。
- 删除:仅**评论作者本人**或 **project 管理者**(`can_manage_project`)。

---

## 5. 贯穿始终的鉴权:Actor 统一模型

`backend/app/core/actor.py` 把「会话用户」和「API token」统一成一个 `Actor`:

- 会话用户 → 隐式拥有 `FULL_SCOPES`,权限走角色(role)判断。
- API token → 显式 scope 集合 + 可选 `project_allowlist`。

```python
def token_allows_project(self, project_slug) -> bool:
    if self.token is None: return True
    allow = self.token.project_allowlist
    if not allow: return True          # 没设白名单 = 整个 workspace
    return project_slug in allow
```

**可学习点:** 端点里不用到处写 `if token ... else user ...`;拿到 `Actor` 后统一 `require_scope()` / `token_allows_project()` / 角色检查,鉴权逻辑集中、可测。

---

## 6. Codex Review 结论:已修复 + 已知限制

对本次「图床 + 评论」的改动做了独立 review。结论:**无 Critical**。以下 3 项已在本轮修复并补了测试:

1. **[High] 资产读取绕过 token 项目白名单(IDOR)**:原先 `GET /assets/<id>` 的 token 分支只校验了 scope + workspace,没校验白名单——一个只允许访问 project A 的 token 能读到同 workspace 里 project B 的图。**已修复**:

   ```python
   if asset.project_id is not None:
       project = db.get(Project, asset.project_id)
       slug = project.slug if project else None
       if slug is None or not actor.token_allows_project(slug):
           raise HTTPException(404, "not_found")
   elif actor.token.project_allowlist:      # 有白名单的 token 不能读无主草稿图
       raise HTTPException(404, "not_found")
   ```

2. **[Medium] 并发同图上传竞态**:`create_asset` 已加 `IntegrityError` 回退(§2.2)。

3. **[Low] `safe_html` 把 `pagedrop://` scheme 洗掉了**:导致 HTML `<img>` 引用图片失效。**已修复**——让 sanitizer 放行我们自己的 scheme(`javascript:` 仍然被剥离):

   ```python
   url_schemes={"http", "https", "mailto", "data", "pagedrop"}
   ```

**尚未处理的已知限制(后续按需加固):**

- **私密 share 链接里的图片打不开**:share 页匿名渲染走 `/public/assets`,但该端点只认 project 可见性,不认 share token/密码证明。私有文档通过 share 链接公开时,图会 404。正解:**签名 URL** 或密码校验后下发**短期 share cookie**。
- **去重跨 project 的归属歧义**:去重键是 `(workspace_id, sha256)`,但 asset 只有一个 `project_id`。同一份字节被另一个 project 复用时,归属仍停留在旧 project,可见性会跟着旧 project 走。彻底解法:拆成「blob 表(按 hash 存字节)+ project_assets 关联表(多对多)」。
- **上传大小是「先全读入内存再校验」**:`asset_max_bytes` 默认 10MB、且信任客户端 MIME。加固方向:流式读取 + 硬上限 + 真正嗅探图片类型 + 响应加 `X-Content-Type-Options: nosniff`。
- **CLI 会读取 `../` / 绝对路径的本地图片**:处理不可信 Markdown 时可能被诱导上传本机任意文件。加固方向:默认要求图片路径落在内容文件目录内,越界需显式 `--unsafe` 之类的开关。

---

## 7. 值得我复用的通用设计点

1. **内容寻址存储**:`sha256` 做主键式去重 + 不可变 + 长缓存,一套逻辑解决去重、缓存、完整性。
2. **逻辑引用而非物理 URL**(`pagedrop://asset/<id>`):获得存储位置无关性 + 鉴权上下文自适应,是「让历史数据不被基础设施变更绑架」的关键。
3. **Protocol 抽象存储后端**:本地盘 → 对象存储零业务改动。
4. **Actor 统一人/机鉴权**:scope + 白名单 + 角色三合一,端点代码干净。
5. **Agent-ready API 设计**:CLI 一条命令封装「上传+改写+发布」;评论 `--json` + 状态筛选,让自动化闭环成立。
6. **并发用唯一约束兜底**,而非「先查后插」;**延迟绑定资源**在发布时收尾认领(`link_referenced_assets`)。

---

*本文由实现 + Codex review 汇总而成,含真实代码片段,供导读与学习。*
