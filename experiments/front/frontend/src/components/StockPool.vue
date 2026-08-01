<template>
  <div class="stock-pool-page">
    <!-- 股票添加工具 -->
    <div class="stock-add-tool">
      <div class="row">
        <el-input
          v-model="searchInput"
          placeholder="输入股票名称或代码，逗号分隔多只"
          size="large"
          clearable
          class="stock-input"
          @keyup.enter="handleSearch"
        />
        <el-button type="primary" size="large" @click="handleSearch">🔍 查询</el-button>
      </div>
      <div v-if="searchResults.length > 0" class="row">
        <div class="result-box has-results">
          <span>{{ resultText }}</span>
        </div>
        <el-button type="success" size="large" @click="handleAddToPool">✓ 确认加入股票池</el-button>
      </div>
    </div>

    <!-- 股票池表格 -->
    <div class="data-table-wrap">
      <div class="table-header">
        <span>📋 我的股票池</span>
        <span class="table-info">昨日行情 · 共 {{ stocks.length }} 只</span>
      </div>
      <el-table :data="stocks" style="width:100%;" stripe header-row-class-name="table-head" @cell-click="handleCellClick">
        <el-table-column prop="stock_name" label="股票名称" min-width="100" />
        <el-table-column label="代码" min-width="120">
          <template #default="{ row }">
            <el-tag size="small">{{ row.ts_code }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="开盘" min-width="80" align="right">
          <template #default="{ row }">{{ row.daily?.open ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="最高" min-width="80" align="right">
          <template #default="{ row }">{{ row.daily?.high ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="最低" min-width="80" align="right">
          <template #default="{ row }">{{ row.daily?.low ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="昨收" min-width="80" align="right">
          <template #default="{ row }">{{ row.daily?.close ?? '-' }}</template>
        </el-table-column>
        <el-table-column label="涨跌幅" min-width="90" align="right">
          <template #default="{ row }">
            <span v-if="row.daily?.pct_chg != null" :class="row.daily.pct_chg >= 0 ? 'tag-up' : 'tag-down'">
              {{ row.daily.pct_chg >= 0 ? '+' : '' }}{{ row.daily.pct_chg?.toFixed(2) }}%
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="涨跌额" min-width="80" align="right">
          <template #default="{ row }">
            <span v-if="row.daily?.change != null" :class="row.daily.change >= 0 ? 'tag-up' : 'tag-down'">
              {{ row.daily.change >= 0 ? '+' : '' }}{{ row.daily.change?.toFixed(2) }}
            </span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column label="成交量(手)" min-width="100" align="right">
          <template #default="{ row }">{{ row.daily?.vol ? (+row.daily.vol).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column label="成交额(千元)" min-width="110" align="right">
          <template #default="{ row }">{{ row.daily?.amount ? (+row.daily.amount).toLocaleString() : '-' }}</template>
        </el-table-column>
        <el-table-column label="换手率" min-width="80" align="right">
          <template #default="{ row }">{{ row.daily?.turnover_rate != null ? row.daily.turnover_rate + '%' : '-' }}</template>
        </el-table-column>
        <el-table-column label="操作" width="70" fixed="right">
          <template #default="{ row }">
            <el-button text type="danger" size="small" @click="handleRemove(row.ts_code)">✕</el-button>
          </template>
        </el-table-column>
      </el-table>
      <div v-if="loading" class="loading-bar">
        <el-skeleton :rows="3" animated />
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { searchStock, resolveStocks, getStockPool, addToPool, removeFromPool } from '../api/index.js'

const searchInput = ref('')
const searchResults = ref([])
const stocks = ref([])
const loading = ref(false)

onMounted(() => {
  loadPool()
})

async function loadPool() {
  try {
    const data = await getStockPool()
    stocks.value = data.stocks || []
  } catch {
    stocks.value = []
  }
}

async function handleSearch() {
  const input = searchInput.value.trim()
  if (!input) return
  const names = input.split(/[,，、\s]+/).filter(Boolean)
  try {
    const data = await resolveStocks(names)
    searchResults.value = data.results || []
    if (searchResults.value.length === 0) {
      ElMessage.warning('未找到匹配的股票，请检查名称')
    }
  } catch {
    ElMessage.error('查询失败')
  }
}

const resultText = ref('')
watch(searchResults, (val) => {
  resultText.value = val.map(r => `${r.name}(${r.ts_code})`).join(' · ')
})

async function handleAddToPool() {
  if (searchResults.value.length === 0) return
  const names = searchResults.value.map(r => r.name)
  try {
    await addToPool(names)
    ElMessage.success(`已加入 ${names.length} 只股票到股票池`)
    searchResults.value = []
    searchInput.value = ''
    loadPool()
  } catch (e) {
    ElMessage.error('加入失败')
  }
}

async function handleRemove(tsCode) {
  try {
    await ElMessageBox.confirm('确定从股票池移除？', '确认')
    await removeFromPool(tsCode)
    ElMessage.success('已移除')
    loadPool()
  } catch { /* cancelled */ }
}

function handleCellClick(row, column) {
  // 点击行不做特殊操作（操作列有按钮）
}
</script>

<style scoped>
.stock-add-tool {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 4px rgba(74,55,40,0.06);
  margin-bottom: 20px;
}
.row { display: flex; gap: 12px; align-items: center; flex-wrap: wrap; }
.row + .row { margin-top: 16px; }
.stock-input { flex: 1; min-width: 180px; }
.result-box {
  flex: 1; min-width: 200px;
  height: 44px; padding: 0 16px;
  background: var(--wood-50);
  border: 1.5px dashed var(--wood-300);
  border-radius: 8px;
  display: flex; align-items: center;
  font-size: 1rem; color: var(--wood-600);
}
.result-box.has-results { border-style: solid; border-color: var(--green-400); color: var(--wood-800); }

.data-table-wrap {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 1px 4px rgba(74,55,40,0.06);
}
.table-header {
  padding: 14px 20px;
  font-size: 0.9rem; font-weight: 600;
  color: var(--wood-600);
  border-bottom: 1px solid var(--wood-100);
  display: flex; align-items: center; justify-content: space-between;
}
.table-info { font-weight: 400; font-size: 0.85rem; color: var(--wood-400); }
:deep(.table-head th) { background: var(--wood-50) !important; color: var(--wood-600); font-weight: 600; }
:deep(.el-table td) { padding: 10px 0; }
.tag-up { color: #C62828; font-weight: 500; }
.tag-down { color: #2E7D32; font-weight: 500; }
.loading-bar { padding: 20px; }
</style>
