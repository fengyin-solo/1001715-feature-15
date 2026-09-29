<template>
  <section class="page" data-module="operator">
    <header class="page-head">
      <div>
        <h2>作业人员管理</h2>
        <p class="page-desc">按作业项目与复审日期确定归属单位；只有本单位管理员能维护，跨单位修改会被拦下并提示。</p>
      </div>
      <div class="page-actions">
        <label class="unit-switch">
          <span>当前值班单位</span>
          <select :value="session.unit" @change="onUnitChange">
            <option v-for="u in units" :key="u" :value="u">{{ u }}</option>
          </select>
        </label>
        <button class="btn primary" type="button" @click="openCreate">登记作业人员</button>
        <button class="btn" type="button" @click="exportRows">导出清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in unitLedger" :key="item.单位" class="stat-card">
        <span class="stat-label">{{ item.单位 }} · 持证人数</span>
        <strong class="stat-value">{{ item.持证人数 }}</strong>
      </article>
      <article class="stat-card">
        <span class="stat-label">证照信息缺失</span>
        <strong class="stat-value">{{ missingCount }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>关键词</span>
        <input v-model="filters.keyword" placeholder="人员编号或姓名" />
      </label>
      <label class="filter-item">
        <span>人员状态</span>
        <select v-model="filters.status">
          <option value="">全部</option>
          <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
        </select>
      </label>
      <label class="filter-item">
        <span>归属单位</span>
        <select v-model="filters.unit">
          <option value="">全部</option>
          <option v-for="u in units" :key="u" :value="u">{{ u }}</option>
        </select>
      </label>
      <label class="filter-item checkbox">
        <input v-model="filters.missing_only" type="checkbox" />
        <span>只看证照缺失</span>
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置</button>
    </form>

    <table class="data-table">
      <thead>
        <tr>
          <th v-for="column in columns" :key="column">{{ column }}</th>
          <th>可执行动作</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="String(row.id)">
          <td v-for="column in columns" :key="column">{{ row[column] ?? '—' }}</td>
          <td class="row-actions">
            <button
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              :disabled="!canModify(row)"
              :title="canModify(row) ? '' : `该人员归属「${row.所属单位 || '未归属'}」，你是「${session.unit}」管理员，无权改动`"
              @click="openAction(action, row)"
            >
              {{ action }}
            </button>
            <button class="link" type="button" @click="toggleDetail(row)">
              {{ expandedId === row.id ? '收起' : '证照/复审' }}
            </button>
          </td>
        </tr>
        <tr v-if="expandedRow" class="detail-row">
          <td :colspan="columns.length + 1">
            <div class="detail-panel">
              <div class="detail-block">
                <h4>有效证照</h4>
                <table class="data-table">
                  <thead>
                    <tr><th>作业项目</th><th>证件编号</th><th>有效期至</th><th>复审日期</th><th>所属单位</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(cert, idx) in expandedRow.certificates" :key="idx">
                      <td>{{ cert.作业项目 }}</td>
                      <td>{{ cert.证件编号 }}</td>
                      <td>{{ cert.有效期至 }}</td>
                      <td>{{ cert.复审日期 }}</td>
                      <td>{{ cert.所属单位 }}</td>
                    </tr>
                    <tr v-if="!expandedRow.certificates || !expandedRow.certificates.length">
                      <td colspan="5" class="empty-state">暂无有效证照</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <div class="detail-block">
                <h4>历史复审记录</h4>
                <table class="data-table">
                  <thead>
                    <tr><th>复审日期</th><th>作业项目</th><th>复审单位</th><th>复审结果</th></tr>
                  </thead>
                  <tbody>
                    <tr v-for="(record, idx) in expandedRow.reviewRecords" :key="idx">
                      <td>{{ record.复审日期 }}</td>
                      <td>{{ record.作业项目 }}</td>
                      <td>{{ record.复审单位 }}</td>
                      <td>{{ record.复审结果 }}</td>
                    </tr>
                    <tr v-if="!expandedRow.reviewRecords || !expandedRow.reviewRecords.length">
                      <td colspan="4" class="empty-state">暂无复审记录</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无作业人员数据，可先登记作业人员</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条作业人员记录</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <div v-if="actionForm" class="modal-mask" @click.self="actionForm = null">
      <div class="modal">
        <h3>{{ actionForm.title }}</h3>
        <p class="modal-sub">{{ actionForm.sub }}</p>
        <label v-for="field in actionForm.fields" :key="field.key" class="filter-item">
          <span>{{ field.label }}</span>
          <input v-model="actionForm.values[field.key]" :placeholder="field.placeholder" />
        </label>
        <div class="modal-actions">
          <button class="btn primary" type="button" @click="submitAction">确认</button>
          <button class="btn ghost" type="button" @click="actionForm = null">取消</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'
import { UNITS, useSessionStore } from '@/stores/session'

type Row = Record<string, any>
type UnitLedgerItem = { 单位: string; 持证人数: number }
type FormField = { key: string; label: string; placeholder: string }

const ENDPOINT = '/api/operator'
const columns = ['人员编号', '人员姓名', '所属单位', '作业项目', '证件编号', '有效期至', '复审日期', '人员状态']
const actions = ['复审', '登记取证', '归属变更', '标记过期', '办理离岗']
const statuses = ['待取证', '在岗持证', '证件过期', '已离岗']
const units = [...UNITS]

const session = useSessionStore()

const rows = ref<Row[]>([])
const total = ref(0)
const unitLedger = ref<UnitLedgerItem[]>([])
const missingCount = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = reactive<Record<string, any>>({ keyword: '', status: '', unit: '', missing_only: false })
const expandedId = ref<number | null>(null)
const expandedRow = ref<Row | null>(null)
const actionForm = ref<{ title: string; sub: string; fields: FormField[]; values: Record<string, string>; action: string; row: Row } | null>(null)

const ACTION_FIELDS: Record<string, FormField[]> = {
  复审: [
    { key: '复审日期', label: '复审日期', placeholder: '如 2026-09-20' },
    { key: '有效期至', label: '有效期至（可选）', placeholder: '如 2028-09-20' },
  ],
  登记取证: [
    { key: '作业项目', label: '作业项目', placeholder: '如 叉车司机' },
    { key: '证件编号', label: '证件编号', placeholder: '证件编号' },
    { key: '有效期至', label: '有效期至', placeholder: '如 2028-09-20' },
    { key: '复审日期', label: '复审日期', placeholder: '如 2026-09-20' },
  ],
  归属变更: [
    { key: '所属单位', label: '转入单位', placeholder: '如 运行二班' },
  ],
}

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  filters.unit = ''
  filters.missing_only = false
  void reload()
}

function onUnitChange(event: Event) {
  session.setUnit((event.target as HTMLSelectElement).value)
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function authHeaders(): Record<string, string> {
  return { 'X-Operator-Unit': encodeURIComponent(session.unit) }
}

/** 只有本单位管理员能维护；未归属人员任意单位可接手。 */
function canModify(row: Row): boolean {
  const unit = String(row['所属单位'] ?? '')
  return !unit || unit === session.unit
}

function openCreate() {
  actionForm.value = {
    title: '登记作业人员',
    sub: '登记后可在「登记取证」中补录证照；必填：人员编号、人员姓名、所属单位。',
    action: 'create',
    row: {},
    fields: [
      { key: '人员编号', label: '人员编号', placeholder: '如 OPER-0006' },
      { key: '人员姓名', label: '人员姓名', placeholder: '如 周某' },
      { key: '所属单位', label: '所属单位', placeholder: '如 运行一班' },
      { key: '作业项目', label: '作业项目（可选）', placeholder: '如 叉车司机' },
      { key: '证件编号', label: '证件编号（可选）', placeholder: '证件编号' },
      { key: '有效期至', label: '有效期至（可选）', placeholder: '如 2028-09-20' },
      { key: '复审日期', label: '复审日期（可选）', placeholder: '如 2026-09-20' },
    ],
    values: {},
  }
}

function openAction(action: string, row: Row) {
  errorMessage.value = ''
  successMessage.value = ''
  const fields = ACTION_FIELDS[action]
  if (!fields) {
    // 标记过期、办理离岗无需填写，直接执行
    void runAction(action, row, {})
    return
  }
  const values: Record<string, string> = {}
  if (action === '归属变更') values['所属单位'] = ''
  actionForm.value = {
    title: action,
    sub: `人员：${row['人员姓名'] ?? ''}（${row['人员编号'] ?? ''}）`,
    action,
    row,
    fields,
    values,
  }
}

async function submitAction() {
  const form = actionForm.value
  if (!form) return
  if (form.action === 'create') {
    await createPerson(form.values)
  } else {
    await runAction(form.action, form.row, form.values)
  }
  actionForm.value = null
}

async function createPerson(values: Record<string, string>) {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '作业人员登记失败')
    }
    successMessage.value = payload.message || '作业人员已登记'
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业人员登记失败'
  }
}

async function runAction(action: string, row: Row, values: Record<string, string>) {
  errorMessage.value = ''
  successMessage.value = ''
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      headers: authHeaders(),
      body: JSON.stringify({ values: { ...values, action } }),
    })
    const payload = await response.json()
    if (!response.ok || payload.ok === false) {
      throw new Error(payload.message || '作业人员动作未生效')
    }
    successMessage.value = payload.message || `作业人员已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业人员操作失败'
  }
}

function toggleDetail(row: Row) {
  if (expandedId.value === row.id) {
    expandedId.value = null
    expandedRow.value = null
  } else {
    expandedId.value = Number(row.id)
    expandedRow.value = row
  }
}

async function loadUnitLedger() {
  try {
    const payload = await request(`${ENDPOINT}/unit-ledger`)
    if (!payload.ok) throw new Error('单位台账读取失败')
    const data = await payload.json()
    unitLedger.value = data.ledger ?? []
    missingCount.value = data.missing ?? 0
  } catch {
    unitLedger.value = []
    missingCount.value = 0
  }
}

async function reload() {
  errorMessage.value = ''
  successMessage.value = ''
  const params = new URLSearchParams()
  if (filters.keyword) params.set('keyword', filters.keyword)
  if (filters.status) params.set('status', filters.status)
  if (filters.unit) params.set('unit', filters.unit)
  if (filters.missing_only) params.set('missing_only', 'true')
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) throw new Error('作业人员列表读取失败')
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    // 展开的行数据同步最新
    if (expandedId.value !== null) {
      expandedRow.value = rows.value.find((r) => Number(r.id) === expandedId.value) ?? null
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '作业人员列表读取失败'
  }
  await loadUnitLedger()
}

onMounted(reload)
</script>

<style scoped>
.unit-switch { display: flex; flex-direction: column; font-size: 12px; color: var(--muted); }
.unit-switch select { margin-top: 2px; padding: 4px 6px; }
.page-actions { display: flex; gap: 8px; align-items: flex-end; }
.checkbox { flex-direction: row; align-items: center; gap: 6px; }
.checkbox span { margin: 0; }
.detail-row { background: #f8fafc; }
.detail-panel { display: flex; flex-direction: column; gap: 12px; padding: 8px; }
.detail-block h4 { margin: 0 0 6px; font-size: 13px; }
.modal-mask { position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45); display: flex; align-items: center; justify-content: center; z-index: 50; }
.modal { background: #fff; border-radius: 10px; padding: 18px 20px; width: 420px; max-width: 92vw; }
.modal h3 { margin: 0 0 4px; }
.modal-sub { color: var(--muted); font-size: 12px; margin: 0 0 12px; }
.modal .filter-item { display: flex; flex-direction: column; margin-bottom: 10px; }
.modal .filter-item span { font-size: 12px; color: var(--muted); }
.modal .filter-item input { padding: 6px 8px; margin-top: 2px; }
.modal-actions { display: flex; gap: 8px; justify-content: flex-end; margin-top: 8px; }
.success-text { color: #15803d; }
.row-actions .link:disabled { color: #94a3b8; cursor: not-allowed; }
</style>
