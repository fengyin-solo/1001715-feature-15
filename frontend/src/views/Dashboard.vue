<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常；持证人数与单位台账同口径。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <div v-if="unitRows.length" class="unit-ledger">
      <h3 class="section-title">各单位持证人数</h3>
      <div class="stat-row">
        <article v-for="row in unitRows" :key="row.单位" class="stat-card">
          <span class="stat-label">{{ row.单位 }}</span>
          <strong class="stat-value">{{ row.持证人数 }}</strong>
        </article>
      </div>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type Overview = {
  cards: { label: string; value: number }[]
  modules: { name: string; created: number; pending: number; abnormal: number }[]
  certifiedByUnit?: Record<string, number>
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<Overview['modules']>([])
const unitRows = ref<{ 单位: string; 持证人数: number }[]>([])

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    unitRows.value = Object.entries(payload.certifiedByUnit ?? {}).map(([单位, 持证人数]) => ({ 单位, 持证人数 }))
  } catch {
    cards.value = [{"label": "业务模块", "value": 0}, {"label": "今日新增", "value": 0}, {"label": "持证人数", "value": 0}]
    moduleRows.value = [{"name": "锅炉设备", "created": 0, "pending": 0, "abnormal": 0}, {"name": "压力容器", "created": 0, "pending": 0, "abnormal": 0}, {"name": "压力管道", "created": 0, "pending": 0, "abnormal": 0}, {"name": "起重机械", "created": 0, "pending": 0, "abnormal": 0}, {"name": "电梯设备", "created": 0, "pending": 0, "abnormal": 0}, {"name": "场内机动车辆", "created": 0, "pending": 0, "abnormal": 0}, {"name": "点检计划", "created": 0, "pending": 0, "abnormal": 0}, {"name": "点检记录", "created": 0, "pending": 0, "abnormal": 0}, {"name": "润滑保养", "created": 0, "pending": 0, "abnormal": 0}, {"name": "定期检验", "created": 0, "pending": 0, "abnormal": 0}, {"name": "检验报告", "created": 0, "pending": 0, "abnormal": 0}, {"name": "隐患登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "整改闭环", "created": 0, "pending": 0, "abnormal": 0}, {"name": "使用登记", "created": 0, "pending": 0, "abnormal": 0}, {"name": "作业人员", "created": 0, "pending": 0, "abnormal": 0}, {"name": "备件器材", "created": 0, "pending": 0, "abnormal": 0}, {"name": "维保合同", "created": 0, "pending": 0, "abnormal": 0}, {"name": "费用结算", "created": 0, "pending": 0, "abnormal": 0}]
    unitRows.value = []
  }
})
</script>
