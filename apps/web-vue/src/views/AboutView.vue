<script setup lang="ts">
const features = [
  { title: "版本不可变", body: "每次发布生成一个不可变版本,历史永远可回溯。" },
  { title: "多端可读", body: "任意设备打开链接即可阅读,无需安装。" },
  { title: "密码 / 过期分享", body: "分享链接可设密码、过期时间与查看次数上限。" },
  { title: "Agent 友好", body: "CLI + 结构化 API,让 AI Agent 直接发布、拉取与协作。" },
  { title: "图文内嵌", body: "图片作为托管资产内嵌进 Markdown / HTML,随文档一起分发。" },
  { title: "评论协作", body: "在文档上留下评论并成串讨论,Agent 也能读取与回复。" },
];
</script>

<template>
  <div class="container about">
    <section class="hero">
      <h1>PageDrop</h1>
      <p class="lede">
        为人与 Agent 打造的、版本不可变的发布与协作平台。
      </p>
    </section>

    <section>
      <h2>核心能力</h2>
      <div class="grid">
        <div v-for="f in features" :key="f.title" class="card feature">
          <strong>{{ f.title }}</strong>
          <p class="muted">{{ f.body }}</p>
        </div>
      </div>
    </section>

    <section>
      <h2>隐私立场</h2>
      <div class="card stack privacy">
        <p>
          <strong>现状:</strong>三档可见性 —
          <span class="badge public">public</span>
          <span class="badge unlisted">unlisted</span>
          <span class="badge private">private</span>。
          private 仅对 workspace 成员可见。
        </p>
        <p>
          <strong>诚实说明:</strong>private 是<em>访问控制</em>。平台运维方在数据库层面技术上可读 —
          我们不夸大它的保密性。
        </p>
        <p>
          <strong>Roadmap:</strong>我们计划提供 <em>Workspace 级零知识加密</em>,届时连平台方都无法读取你的内容。
          是否推进将取决于用户的真实需求。
        </p>
      </div>
    </section>

    <section class="links">
      <a href="https://github.com/hztBUAA/pagedrop" target="_blank" rel="noopener" class="btn">
        GitHub
      </a>
    </section>
  </div>
</template>

<style scoped>
.about {
  max-width: 860px;
  padding-bottom: 3rem;
}
.hero {
  text-align: center;
  padding: 2.5rem 0 1.5rem;
}
.hero h1 {
  font-size: 2.6rem;
  margin: 0 0 0.5rem;
}
.lede {
  font-size: 1.15rem;
  color: var(--text-dim);
  margin: 0;
}
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 0.75rem;
}
.feature p {
  margin: 0.35rem 0 0;
  font-size: 0.9rem;
}
.privacy p {
  margin: 0;
}
.privacy em {
  font-style: normal;
  text-decoration: underline;
}
.links {
  margin-top: 1.5rem;
}
</style>
