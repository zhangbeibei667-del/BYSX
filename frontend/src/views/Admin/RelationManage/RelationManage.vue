<template>
  <div class="relation-manage">
    <h1>图谱关系维护</h1>
    <p>此页面用于管理实体间的关系三元组，待完善。</p>
    <div class="placeholder">
      <h3>功能规划：</h3>
      <ul>
        <li>关系三元组表格展示（源实体、关系、目标实体）</li>
        <li>下拉选择源实体、目标实体、关系类型</li>
        <li>新增/删除关系功能</li>
        <li>批量清除无效关系</li>
      </ul>
    </div>
  </div>
</template>

<script setup lang="ts">
// 关系管理页面 - 待完善
</script>

<style scoped>
.relation-manage {
  padding: 20px;
}

.placeholder {
  margin-top: 30px;
  padding: 20px;
  background-color: #f5f5f5;
  border-radius: 8px;
}

.placeholder ul {
  margin-top: 10px;
}

.placeholder li {
  margin-bottom: 8px;
}
</style>