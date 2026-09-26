<template>
  <section class="page" data-module="occupy">
    <header class="page-head">
      <div>
        <h2>占道施工管理</h2>
        <p class="page-desc">维护占道施工，围绕施工编号、施工位置、占用范围、施工内容做登记、筛选与状态流转。</p>
      </div>
      <div class="page-actions">
        <button class="btn primary" type="button" @click="showCreate = !showCreate">
          {{ showCreate ? '收起登记表单' : '登记占道施工' }}
        </button>
        <button class="btn" type="button" @click="exportRows">导出占道施工清单</button>
      </div>
    </header>

    <div class="stat-row">
      <article v-for="item in stats" :key="item.label" class="stat-card">
        <span class="stat-label">{{ item.label }}</span>
        <strong class="stat-value">{{ item.value }}</strong>
      </article>
    </div>

    <form v-if="showCreate" class="filter-bar create-bar" @submit.prevent="submitCreate">
      <label v-for="field in createFields" :key="field" class="filter-item">
        <span>{{ field }}{{ requiredFields.includes(field) ? '（必填）' : '' }}</span>
        <input v-model="createForm[field]" :placeholder="`填写${field}`" />
      </label>
      <button class="btn primary" type="submit">提交占道申请</button>
    </form>

    <form class="filter-bar" @submit.prevent="reload">
      <label class="filter-item">
        <span>施工编号</span>
        <input v-model="filters.keyword" placeholder="按施工编号检索" />
      </label>
      <label class="filter-item">
        <span>施工状态</span>
        <select v-model="filters.status">
          <option value="">全部状态</option>
          <option v-for="status in statuses" :key="status" :value="status">{{ status }}</option>
        </select>
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
              v-for="action in actions"
              :key="action"
              class="link"
              type="button"
              @click="runAction(action, row)"
            >
              {{ action }}
            </button>
          </td>
        </tr>
        <tr v-if="!rows.length">
          <td :colspan="columns.length + 1" class="empty-state">暂无占道施工数据，可先登记占道施工</td>
        </tr>
      </tbody>
    </table>

    <footer class="page-foot">
      <span>共 {{ total }} 条占道施工记录</span>
      <span v-if="noticeMessage" class="notice-text">{{ noticeMessage }}</span>
      <span v-if="errorMessage" class="error-text">{{ errorMessage }}</span>
    </footer>
  </section>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'

import { request } from '@/api/client'

type Row = Record<string, string | number | null>

const ENDPOINT = '/api/occupy'
const columns = ["施工编号", "施工位置", "占用范围", "施工内容", "申请人", "审批人", "占用期限", "施工状态"]
const actions = ["审批通过", "开始施工", "完工确认", "恢复通行"]
const statuses = ["待审批", "已批准", "施工中", "已完工", "已恢复"]
const requiredFields = ["施工编号", "施工位置", "占用范围"]
const createFields = [...requiredFields, "施工内容", "申请人", "占用期限"]

const rows = ref<Row[]>([])
const total = ref(0)
const stats = ref(statuses.map((status) => ({ label: `${status}占道`, value: 0 })))
const errorMessage = ref('')
const noticeMessage = ref('')
const showCreate = ref(false)
const filters = reactive({ keyword: '', status: '' })
const createForm = reactive<Record<string, string>>({})

function resetFilters() {
  filters.keyword = ''
  filters.status = ''
  void reload()
}

function exportRows() {
  window.open(`${ENDPOINT}/export`, '_blank')
}

async function submitCreate() {
  errorMessage.value = ''
  noticeMessage.value = ''
  try {
    const response = await request(ENDPOINT, {
      method: 'POST',
      body: JSON.stringify({ values: { ...createForm } }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '占道申请提交失败')
    }
    noticeMessage.value = payload.message ?? '占道施工已登记'
    Object.keys(createForm).forEach((key) => delete createForm[key])
    showCreate.value = false
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '占道申请提交失败'
  }
}

async function runAction(action: string, row: Row) {
  errorMessage.value = ''
  noticeMessage.value = ''
  const values: Record<string, string> = { action }
  if (action === '审批通过') {
    const approver = window.prompt('填写审批人（留空则暂不记录）', '王海涛（道桥管理科）')
    if (approver) {
      values['审批人'] = approver
    }
  }
  try {
    const response = await request(`${ENDPOINT}/${row.id}/actions`, {
      method: 'POST',
      body: JSON.stringify({ values }),
    })
    const payload = await response.json()
    if (!response.ok || !payload.ok) {
      throw new Error(payload.message ?? payload.detail ?? '占道施工动作未生效，请稍后重试')
    }
    noticeMessage.value = payload.message ?? `占道施工已${action}`
    await reload()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '占道施工操作失败'
  }
}

async function reload() {
  errorMessage.value = ''
  const query = new URLSearchParams()
  if (filters.keyword) query.set('keyword', filters.keyword)
  if (filters.status) query.set('status', filters.status)
  try {
    const response = await request(`${ENDPOINT}?${query.toString()}`)
    if (!response.ok) {
      throw new Error('占道施工列表读取失败')
    }
    const payload = await response.json()
    rows.value = payload.items ?? []
    total.value = payload.total ?? rows.value.length
    await refreshStats()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : '占道施工列表读取失败'
  }
}

async function refreshStats() {
  try {
    const response = await request(`${ENDPOINT}?size=200`)
    if (!response.ok) return
    const payload = await response.json()
    const all: Row[] = payload.items ?? []
    stats.value = statuses.map((status) => ({
      label: `${status}占道`,
      value: all.filter((row) => row.status === status).length,
    }))
  } catch {
    // 统计卡片失败不阻断列表，保持静默
  }
}

onMounted(reload)
</script>

<style scoped>
.create-bar {
  background: #fff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 10px 12px;
}
.filter-item select {
  min-width: 120px;
  padding: 4px 6px;
  border: 1px solid var(--border);
  border-radius: 6px;
}
.notice-text {
  color: #067647;
}
</style>
