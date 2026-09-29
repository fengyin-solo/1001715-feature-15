<template>
  <section class="page" data-module="operator">
    <header class="page-head">
      <div>
        <h2>作业人员证照归属管理</h2>
        <p class="page-desc">按作业项目与复审日期把人员划到所属单位，只有本单位管理员可维护；证照到期自动转「证件过期」，复审完成恢复「在岗持证」。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记作业人员</button>
        <button class="btn" type="button" @click="exportRows">导出人员清单</button>
      </div>
    </header>

    <div class="scope-bar">
      <label class="filter-item">
        <span>当前管理员所属单位</span>
        <select :value="session.adminUnit" @change="switchUnit(($event.target as HTMLSelectElement).value)">
          <option v-for="unit in units" :key="unit" :value="unit">{{ unit }}</option>
        </select>
      </label>
      <span class="scope-hint">切换单位即按该单位管理员身份操作，跨单位修改会被后端拦下</span>
    </div>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <nav class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab"
        :class="{ active: activeTab === tab.key }"
        type="button"
        @click="switchTab(tab.key)"
      >
        {{ tab.label }}
      </button>
    </nav>

    <!-- 单位台账 -->
    <table v-if="activeTab === 'ledger'" class="data-table">
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
      </tbody>
    </table>

    <!-- 人员列表：本单位 / 全部 / 证照缺失 共用同一张表 -->
    <template v-else-if="activeTab !== 'reviews'">
      <form class="filter-bar" @submit.prevent="reload">
        <label class="filter-item">
          <span>关键字</span>
          <input v-model="keyword" placeholder="按人员编号或姓名检索" />
        </label>
        <label class="filter-item">
          <span>人员状态</span>
          <select v-model="statusFilter">
            <option value="">全部状态</option>
            <option v-for="s in statuses" :key="s" :value="s">{{ s }}</option>
          </select>
        </label>
        <button class="btn" type="submit">查询</button>
        <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
      </form>

      <table class="data-table">
        <thead>
          <tr>
            <th v-for="column in columns" :key="column">{{ column }}</th>
            <th>证照份数</th>
            <th>维护操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in rows" :key="String(row.id)">
            <td v-for="column in columns" :key="column">
              <span v-if="column === '人员状态'" class="status-tag" :class="statusClass(row['人员状态'])">{{ row[column] ?? '—' }}</span>
              <template v-else>{{ row[column] ?? '—' }}</template>
            </td>
            <td>{{ row['证照份数'] }}</td>
            <td class="row-actions">
              <template v-if="canMaintain(row)">
                <button class="link" type="button" @click="openReview(row)">复审</button>
                <button class="link" type="button" @click="openCert(row)">补录证照</button>
                <button
                  v-if="row['人员状态'] !== '已离岗'"
                  class="link danger"
                  type="button"
                  @click="runLeave(row)"
                >办理离岗</button>
              </template>
              <span v-else class="locked-text">归属{{ row['归属单位'] }}，本单位不可改</span>
            </td>
          </tr>
          <tr v-if="!rows.length">
            <td :colspan="columns.length + 2" class="empty-state">暂无符合条件的作业人员</td>
          </tr>
        </tbody>
      </table>
    </template>

    <!-- 复审历史：按当时单位快照留档 -->
    <div v-if="activeTab === 'reviews'" class="filter-bar">
      <label class="filter-item">
        <span>留档单位</span>
        <select v-model="reviewUnitScope">
          <option :value="session.adminUnit">仅本单位原档记录（{{ session.adminUnit }}）</option>
          <option value="">全部单位</option>
        </select>
      </label>
    </div>
    <table v-if="activeTab === 'reviews'" class="data-table">
      <thead>
        <tr><th>复审日期</th><th>原归属单位</th><th>人员编号</th><th>人员姓名</th><th>作业项目</th><th>证件编号</th><th>复审后有效期至</th></tr>
      </thead>
      <tbody>
        <tr v-for="row in reviewRows" :key="String(row.id)">
          <td>{{ row['复审日期'] }}</td>
          <td>{{ row['归属单位'] }}</td>
          <td>{{ row['人员编号'] }}</td>
          <td>{{ row['人员姓名'] }}</td>
          <td>{{ row['作业项目'] }}</td>
          <td>{{ row['证件编号'] }}</td>
          <td>{{ row['有效期至'] }}</td>
        </tr>
        <tr v-if="!reviewRows.length">
          <td colspan="7" class="empty-state">暂无复审记录</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条记录{{ activeTab !== 'reviews' ? '，第 ' + page + ' 页' : '' }}</span>
      <span v-if="feedback.ok" class="success-text">{{ feedback.message }}</span>
      <span v-else-if="feedback.message" class="error-text">{{ feedback.message }}</span>
    </footer>

    <!-- 登记作业人员 -->
    <div v-if="createOpen" class="modal-mask" @click.self="createOpen = false">
      <form class="modal" @submit.prevent="submitCreate">
        <h3>登记作业人员</h3>
        <p class="modal-hint">新登记人员尚无有效证照，会自动进入「证照信息缺失」清单，由登记单位补录。</p>
        <label v-for="field in createFields" :key="field" class="filter-item">
          <span>{{ field }}</span>
          <input v-model="createForm[field]" required />
        </label>
        <label class="filter-item">
          <span>作业项目（可选）</span>
          <select v-model="createForm['作业项目']">
            <option value="">暂不指定</option>
            <option v-for="item in projectOptions" :key="item['作业项目']" :value="item['作业项目']">
              {{ item['作业项目'] }}（{{ item['所属单位'] }}）
            </option>
          </select>
        </label>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="createOpen = false">取消</button>
          <button class="btn primary" type="submit">确认登记</button>
        </div>
      </form>
    </div>

    <!-- 补录证照 -->
    <div v-if="certOpen" class="modal-mask" @click.self="certOpen = false">
      <form class="modal" @submit.prevent="submitCert">
        <h3>为「{{ certTarget?.['人员姓名'] }}」补录证照</h3>
        <label class="filter-item">
          <span>作业项目 *</span>
          <select v-model="certForm['作业项目']" required>
            <option value="" disabled>请选择</option>
            <option v-for="item in projectOptions" :key="item['作业项目']" :value="item['作业项目']">
              {{ item['作业项目'] }}（{{ item['所属单位'] }}）
            </option>
          </select>
        </label>
        <label class="filter-item"><span>证件编号 *</span><input v-model="certForm['证件编号']" required /></label>
        <label class="filter-item"><span>有效期至 *</span><input v-model="certForm['有效期至']" type="date" required /></label>
        <label class="filter-item"><span>复审日期 *</span><input v-model="certForm['复审日期']" type="date" required /></label>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="certOpen = false">取消</button>
          <button class="btn primary" type="submit">保存证照</button>
        </div>
      </form>
    </div>

    <!-- 复审 -->
    <div v-if="reviewOpen" class="modal-mask" @click.self="reviewOpen = false">
      <form class="modal" @submit.prevent="submitReview">
        <h3>复审：「{{ reviewTarget?.['人员姓名'] }}」</h3>
        <p class="modal-hint">当前证件 {{ reviewTarget?.['证件编号'] }}，复审完成后状态自动变为在岗持证；有效期至留空则按原周期顺延。</p>
        <label class="filter-item"><span>复审日期 *</span><input v-model="reviewForm['复审日期']" type="date" required /></label>
        <label class="filter-item"><span>新有效期至（可选）</span><input v-model="reviewForm['有效期至']" type="date" /></label>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="reviewOpen = false">取消</button>
          <button class="btn primary" type="submit">提交复审</button>
        </div>
      </form>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { request } from '@/api/client'
import { useSessionStore } from '@/stores/session'

type Row = Record<string, string | number | null>
type LedgerRow = { '所属单位': string; '人员总数': number; '持证人数': number; '证件过期': number; '证照缺失': number }
type ProjectOption = { '作业项目': string; '所属单位': string }
type Feedback = { ok: boolean; message: string }

const ENDPOINT = '/api/operator'
const columns = ['人员编号', '人员姓名', '归属单位', '作业项目', '证件编号', '有效期至', '复审日期', '人员状态']
const statuses = ['待取证', '在岗持证', '证件过期', '已离岗']
const tabs = [
  { key: 'mine', label: '本单位人员' },
  { key: 'all', label: '全部人员（跨单位只读）' },
  { key: 'missing', label: '证照信息缺失' },
  { key: 'reviews', label: '复审历史（原单位留档）' },
  { key: 'ledger', label: '单位台账' },
] as const

const session = useSessionStore()
const activeTab = ref<(typeof tabs)[number]['key']>('mine')
const units = ref<string[]>([])
const projectOptions = ref<ProjectOption[]>([])
const rows = ref<Row[]>([])
const reviewRows = ref<Row[]>([])
const ledgerRows = ref<LedgerRow[]>([])
const total = ref(0)
const page = ref(1)
const keyword = ref('')
const statusFilter = ref('')
const reviewUnitScope = ref('')  // 空串表示全部单位
const feedback = ref<Feedback>({ ok: false, message: '' })

const createFields = ['人员编号', '人员姓名', '所属单位']
const createOpen = ref(false)
const createForm = ref<Record<string, string>>({ '人员编号': '', '人员姓名': '', '所属单位': session.adminUnit, '作业项目': '' })
const certOpen = ref(false)
const certTarget = ref<Row | null>(null)
const certForm = ref<Record<string, string>>({ '作业项目': '', '证件编号': '', '有效期至': '', '复审日期': '' })
const reviewOpen = ref(false)
const reviewTarget = ref<Row | null>(null)
const reviewForm = ref<Record<string, string>>({ '复审日期': '', '有效期至': '' })

const stats = computed(() => {
  const mine = ledgerRows.value.find((row) => row['所属单位'] === session.adminUnit)
  const certifiedTotal = ledgerRows.value.reduce((sum, row) => sum + row['持证人数'], 0)
  return [
    { label: `本单位持证（${session.adminUnit}）`, value: mine?.['持证人数'] ?? 0 },
    { label: '本单位证件过期', value: mine?.['证件过期'] ?? 0 },
    { label: '本单位证照缺失', value: mine?.['证照缺失'] ?? 0 },
    { label: '全平台持证人数', value: certifiedTotal },
  ]
})

function statusClass(status: string | number | null | undefined): string {
  if (status === '在岗持证') return 'status-ok'
  if (status === '证件过期') return 'status-expired'
  if (status === '已离岗') return 'status-left'
  return 'status-pending'
}

function canMaintain(row: Row): boolean {
  return String(row['归属单位'] ?? '') === session.adminUnit && row['人员状态'] !== '已离岗'
}

function switchTab(key: (typeof tabs)[number]['key']) {
  activeTab.value = key
  if (key === 'reviews') reviewUnitScope.value = ''
  void reload()
}

function switchUnit(unit: string) {
  session.setAdminUnit(unit)
  createForm.value['所属单位'] = unit
  void reload()
}

async function loadMeta() {
  const response = await request(`${ENDPOINT}/projects`)
  const payload = (await response.json()) as { items: ProjectOption[]; units: string[] }
  projectOptions.value = payload.items
  units.value = payload.units
  if (!units.value.includes(session.adminUnit) && units.value[0]) {
    session.setAdminUnit(units.value[0])
  }
}

async function loadLedger() {
  const response = await request(`${ENDPOINT}/ledger`)
  const payload = (await response.json()) as { items: LedgerRow[] }
  ledgerRows.value = payload.items
}

async function loadReviews() {
  const params = new URLSearchParams()
  if (reviewUnitScope.value) params.set('unit', reviewUnitScope.value)
  const response = await request(`${ENDPOINT}/reviews?${params.toString()}`)
  reviewRows.value = ((await response.json()) as { items: Row[] }).items
}

async function reload() {
  feedback.value = { ok: false, message: '' }
  await loadLedger()
  if (activeTab.value === 'reviews') {
    await loadReviews()
    return
  }
  if (activeTab.value === 'ledger') return
  const params = new URLSearchParams({ page: String(page.value), size: '50' })
  if (activeTab.value === 'mine') params.set('unit', session.adminUnit)
  if (activeTab.value === 'missing') params.set('missing', 'true')
  if (keyword.value.trim()) params.set('keyword', keyword.value.trim())
  if (statusFilter.value) params.set('status', statusFilter.value)
  try {
    const response = await request(`${ENDPOINT}?${params.toString()}`)
    if (!response.ok) throw new Error('作业人员列表读取失败')
    const payload = (await response.json()) as { items: Row[]; total: number }
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    feedback.value = { ok: false, message: error instanceof Error ? error.message : '列表读取失败' }
  }
}

function resetFilters() {
  keyword.value = ''
  statusFilter.value = ''
  page.value = 1
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function openCreate() {
  createForm.value = { '人员编号': '', '人员姓名': '', '所属单位': session.adminUnit, '作业项目': '' }
  createOpen.value = true
}

async function submitCreate() {
  const result = await postAction('', createForm.value)
  if (result) {
    createOpen.value = false
    await reload()
  }
}

function openCert(row: Row) {
  certTarget.value = row
  certForm.value = { '作业项目': '', '证件编号': '', '有效期至': '', '复审日期': '' }
  certOpen.value = true
}

async function submitCert() {
  if (!certTarget.value) return
  const result = await postAction(`/${certTarget.value.id}/certificates`, certForm.value)
  if (result) {
    certOpen.value = false
    await reload()
  }
}

function openReview(row: Row) {
  reviewTarget.value = row
  reviewForm.value = { '复审日期': new Date().toISOString().slice(0, 10), '有效期至': '' }
  reviewOpen.value = true
}

async function submitReview() {
  if (!reviewTarget.value) return
  const values: Record<string, string> = { '复审日期': reviewForm.value['复审日期'] }
  if (reviewForm.value['有效期至']) values['有效期至'] = reviewForm.value['有效期至']
  const result = await postAction(`/${reviewTarget.value.id}/reviews`, values)
  if (result) {
    reviewOpen.value = false
    await Promise.all([reload(), loadReviews()])
  }
}

async function runLeave(row: Row) {
  await postAction(`/${row.id}/leave`, {})
  await reload()
}

async function postAction(path: string, values: Record<string, string>): Promise<boolean> {
  try {
    const response = await request(`${ENDPOINT}${path}`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = (await response.json()) as { ok: boolean; message: string }
    feedback.value = { ok: payload.ok, message: payload.message }
    return payload.ok
  } catch (error) {
    feedback.value = { ok: false, message: error instanceof Error ? error.message : '操作未送达' }
    return false
  }
}

onMounted(async () => {
  await loadMeta()
  await reload()
})
</script>

<style scoped>
.scope-bar {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.scope-hint { font-size: 12px; color: var(--muted); }
.tab-bar { display: flex; gap: 4px; margin-bottom: 10px; flex-wrap: wrap; }
.tab { border: 1px solid var(--border); background: #fff; border-radius: 6px 6px 0 0; padding: 6px 14px; cursor: pointer; font-size: 13px; }
.tab.active { background: var(--brand); border-color: var(--brand); color: #fff; }
.status-tag { padding: 1px 8px; border-radius: 10px; font-size: 12px; }
.status-ok { background: #e7f6ec; color: #1a7f37; }
.status-expired { background: #fdecec; color: #b42318; }
.status-left { background: #eef1f5; color: #64748b; }
.status-pending { background: #fff6e0; color: #b25e09; }
.locked-text { color: var(--muted); font-size: 12px; }
.link.danger { color: #b42318; }
.success-text { color: #1a7f37; }
.modal-mask {
  position: fixed; inset: 0; background: rgba(15, 23, 42, 0.45);
  display: flex; align-items: center; justify-content: center; z-index: 20;
}
.modal {
  background: #fff; border-radius: 10px; padding: 18px 20px;
  width: 420px; display: flex; flex-direction: column; gap: 10px;
}
.modal h3 { margin: 0; font-size: 15px; }
.modal-hint { margin: 0; font-size: 12px; color: var(--muted); }
.modal-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 6px; }
</style>
