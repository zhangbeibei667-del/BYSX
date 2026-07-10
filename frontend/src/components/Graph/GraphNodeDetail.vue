<template>
  <div class="graph-node-detail">
    <div class="placeholder">
      <h3>节点详情弹窗组件</h3>
      <p>此组件用于展示图谱节点详细信息，待完善。</p>
      <ul>
        <li>节点属性展示（名称、类型、属性等）</li>
        <li>关联关系列表</li>
        <li>相关文献链接</li>
        <li>编辑和收藏功能</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
// 节点详情弹窗组件 - 待完善
</script>

<style scoped>
.graph-node-detail {
  width: 100%;
  min-height: 200px;
  border: 1px solid #ddd;
  border-radius: 8px;
  background-color: #f9f9f9;
}

.placeholder {
  padding: 20px;
  text-align: center;
}

.placeholder ul {
  margin-top: 10px;
  text-align: left;
  display: inline-block;
}

.placeholder li {
  margin-bottom: 8px;
}
</style>