<template>
  <section class="page">
    <header class="page-head">
      <div>
        <h2>运营概览</h2>
        <p class="page-desc">汇总各业务模块的关键指标，先看总量再看异常。持证人数与作业人员单位台账来自同一份数据。</p>
      </div>
    </header>
    <div class="stat-row">
      <article v-for="card in cards" :key="card.label" class="stat-card">
        <span class="stat-label">{{ card.label }}</span>
        <strong class="stat-value">{{ card.value }}</strong>
      </article>
    </div>
    <table class="data-table">
      <thead>
        <tr><th>业务模块</th><th>今日新增</th><th>待处理</th><th>异常量</th><th v-if="hasCertified">持证人数</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in moduleRows" :key="row.name">
          <td>{{ row.name }}</td>
          <td>{{ row.created }}</td>
          <td>{{ row.pending }}</td>
          <td>{{ row.abnormal }}</td>
          <td v-if="hasCertified">{{ row['持证人数'] ?? '—' }}</td>
        </tr>
      </tbody>
    </table>

    <h3 class="ledger-title">作业人员持证台账（按归属单位）</h3>
    <table class="data-table">
      <thead>
        <tr><th>所属单位</th><th>人员总数</th><th>持证人数</th><th>证件过期</th><th>证照缺失</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in ledgerRows" :key="row['所属单位']">
          <td>{{ row['所属单位'] }}</td>
          <td>{{ row['人员总数'] }}</td>
          <td><strong>{{ row['持证人数'] }}</strong></td>
          <td>{{ row['证件过期'] }}</td>
          <td>{{ row['证照缺失'] }}</td>
        </tr>
        <tr v-if="!ledgerRows.length">
          <td colspan="5" class="empty-state">暂无台账数据</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { fetchJson } from '@/api/client'

type ModuleRow = {
  name: string
  created: number
  pending: number
  abnormal: number
  '持证人数'?: number
}
type LedgerRow = { '所属单位': string; '人员总数': number; '持证人数': number; '证件过期': number; '证照缺失': number }
type Overview = {
  cards: { label: string; value: number }[]
  modules: ModuleRow[]
  operator_ledger?: LedgerRow[]
}

const cards = ref<Overview['cards']>([])
const moduleRows = ref<ModuleRow[]>([])
const ledgerRows = ref<LedgerRow[]>([])
const hasCertified = computed(() => moduleRows.value.some((row) => row['持证人数'] !== undefined))

onMounted(async () => {
  try {
    const payload = await fetchJson<Overview>('/api/overview')
    cards.value = payload.cards
    moduleRows.value = payload.modules
    ledgerRows.value = payload.operator_ledger ?? []
  } catch {
    cards.value = [
      { label: '业务模块', value: 0 },
      { label: '今日新增', value: 0 },
      { label: '持证作业人员', value: 0 },
    ]
    moduleRows.value = []
  }
})
</script>

<style scoped>
.ledger-title { font-size: 14px; margin: 18px 0 8px; }
</style>
