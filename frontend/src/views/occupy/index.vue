<template>
  <section class="page" data-module="occupy">
    <header class="page-head">
      <div>
        <h2>占道施工管理</h2>
        <p class="page-desc">维护占道施工，围绕施工编号、施工位置、占用范围、施工内容做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="openCreate">登记占道施工</button>
        <button class="btn" type="button" @click="exportRows">导出占道施工清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form class="filter-bar" @submit.prevent="reload">
      <label v-for="field in filterFields" :key="field" class="filter-item">
        <span>{{ field }}</span>
        <input v-model="filters[field]" :placeholder="`按${field}检索`" />
      </label>
      <button class="btn" type="submit">查询</button>
      <button class="btn ghost" type="button" @click="resetFilters">重置条件</button>
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
          <td v-for="column in columns" :key="column">{{ row[column] || '—' }}</td>
          <td class="row-actions">
            <button
              v-if="nextAction(String(row.status))"
              class="link"
              type="button"
              @click="onAction(String(nextAction(String(row.status))), row)"
            >
              {{ nextAction(String(row.status)) }}
            </button>
            <span v-else class="page-desc">已终结</span>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无占道施工数据，可先登记占道施工</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条占道施工记录 · 链路：待审批 → 已批准 → 施工中 → 已完工 → 已恢复</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
      <span v-else-if="successMessage" class="success-text">{{ successMessage }}</span>
    </footer>

    <!-- 登记占道施工 -->
    <div v-if="creating" class="modal-mask" @click.self="closeModals">
      <div class="modal-card">
        <h3 class="modal-title">登记占道施工</h3>
        <div class="form-grid">
          <label v-for="field in createFields" :key="field.key">
            <span>{{ field.label }}{{ field.required ? ' *' : '' }}</span>
            <input v-model="createForm[field.key]" :placeholder="field.placeholder" />
          </label>
        </div>
        <p class="form-error">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeModals">取消</button>
          <button class="btn primary" type="button" @click="submitCreate">提交申请</button>
        </div>
      </div>
    </div>

    <!-- 审批通过：补审批人与占用期限 -->
    <div v-if="approvingRow" class="modal-mask" @click.self="closeModals">
      <div class="modal-card">
        <h3 class="modal-title">审批通过 · {{ approvingRow['施工编号'] }}</h3>
        <div class="form-grid">
          <label>
            <span>审批人 *</span>
            <input v-model="approveForm['审批人']" placeholder="如：市政设施管理处·王海涛" />
          </label>
          <label>
            <span>占用期限 *</span>
            <input v-model="approveForm['占用期限']" placeholder="如：2026-10-01 至 2026-10-10" />
          </label>
        </div>
        <p class="form-error">{{ formError }}</p>
        <div class="modal-actions">
          <button class="btn ghost" type="button" @click="closeModals">取消</button>
          <button class="btn primary" type="button" @click="submitApprove">确认审批通过</button>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null | undefined>

const ENDPOINT = '/api/occupy'
const columns = ["施工编号", "施工位置", "占用范围", "施工内容", "申请人", "审批人", "占用期限", "审批时间", "施工状态"]
// 状态机：每行只显示当前状态的「下一动作」，与后端逐级流转一致。
const NEXT_ACTION: Record<string, string | null> = {
  待审批: '审批通过',
  已批准: '开始施工',
  施工中: '施工完成',
  已完工: '恢复通行',
  已恢复: null,
}

const rows = ref<Row[]>([])
const total = ref(0)
const errorMessage = ref('')
const successMessage = ref('')
const filters = ref<Record<string, string>>({})
const filterFields = columns.slice(0, 3)

const creating = ref(false)
const approvingRow = ref<Row | null>(null)
const formError = ref('')

const createFields = [
  { key: '施工编号', label: '施工编号', required: true, placeholder: '如：OCCU-2026-010' },
  { key: '施工位置', label: '施工位置', required: true, placeholder: '如：某大道某路口' },
  { key: '占用范围', label: '占用范围', required: true, placeholder: '如：占用一条机动车道，长约100米' },
  { key: '施工内容', label: '施工内容', required: false, placeholder: '如：管道改造开挖' },
  { key: '申请人', label: '申请人', required: true, placeholder: '如：施工单位·联系人' },
] as const
const createForm = reactive<Record<string, string>>({})
const approveForm = reactive<Record<string, string>>({ '审批人': '', '占用期限': '' })

const stats = computed(() => [
  { label: '待审批占道', value: countBy('待审批') },
  { label: '施工中占道', value: countBy('施工中') },
  { label: '已完工占道', value: countBy('已完工') },
  { label: '已恢复占道', value: countBy('已恢复') },
])

function countBy(status: string): number {
  return rows.value.filter((row) => String(row.status) === status).length
}

function nextAction(status: string): string | null {
  return NEXT_ACTION[status] ?? null
}

function flashSuccess(message: string) {
  successMessage.value = message
  errorMessage.value = ''
}

function resetFilters() {
  filters.value = {}
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

function closeModals() {
  creating.value = false
  approvingRow.value = null
  formError.value = ''
}

function openCreate() {
  Object.keys(createForm).forEach((key) => delete createForm[key])
  formError.value = ''
  creating.value = true
}

async function submitCreate() {
  formError.value = ''
  const values: Record<string, string> = {}
  for (const field of createFields) values[field.key] = (createForm[field.key] ?? '').trim()
  try {
    const response = await request(ENDPOINT, { method: 'POST', body: JSON.stringify({ values }) })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      formError.value = payload.message || '占道施工登记失败'
      return
    }
    closeModals()
    flashSuccess('占道申请已提交，当前状态：待审批')
    await reload()
  } catch (error) {
    formError.value = error instanceof Error ? error.message : '占道施工登记失败'
  }
}

function onAction(action: string, row: Row) {
  errorMessage.value = ''
  if (action === '审批通过') {
    approvingRow.value = row
    approveForm['审批人'] = ''
    approveForm['占用期限'] = ''
    formError.value = ''
    return
  }
  void runAction(action, row, {})
}

async function submitApprove() {
  if (!approvingRow.value) return
  formError.value = ''
  await runAction('审批通过', approvingRow.value, {
    '审批人': approveForm['审批人'].trim(),
    '占用期限': approveForm['占用期限'].trim(),
  })
  if (!errorMessage.value) closeModals()
}

async function runAction(action: string, row: Row, extra: Record<string, string>) {
  try {
    const response = await request(`${ENDPOINT}/${String(row.id)}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values: { action, ...extra } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      errorMessage.value = payload.message || '占道施工动作未生效，请稍后重试'
      successMessage.value = ''
      return
    }
    flashSuccess(payload.message || `动作「${action}」已生效`)
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '占道施工操作失败'
    successMessage.value = ''
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams(filters.value as Record<string, string>).toString()
  try {
    const response = await request(`${ENDPOINT}?${query}`)
    if (!response.ok) {
      throw new Error('占道施工列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '占道施工列表读取失败'
  }
}

onMounted(reload)
</script>
