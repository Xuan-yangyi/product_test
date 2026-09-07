<template>
  <div class="results-view">
    <h2 class="page-title">测试结果</h2>

    <el-card shadow="never" class="filter-card">
      <el-form :inline="true" :model="filters" size="small">
        <el-form-item label="序列号">
          <el-input v-model="filters.serial_number" placeholder="SN" clearable />
        </el-form-item>
        <el-form-item label="测试类型">
          <el-select v-model="filters.test_type" placeholder="全部" clearable>
            <el-option v-for="t in testTypes" :key="t.type" :label="t.label" :value="t.type" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" placeholder="全部" clearable>
            <el-option label="通过" value="completed" />
            <el-option label="失败" value="failed" />
            <el-option label="运行中" value="running" />
            <el-option label="已停止" value="stopped" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="search">查询</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never" class="table-card">
      <el-table :data="results" style="width: 100%" v-loading="loading" size="small">
        <el-table-column prop="test_id" label="测试ID" width="120" />
        <el-table-column prop="test_type" label="测试类型" width="120" />
        <el-table-column prop="product_model" label="产品型号" width="140" />
        <el-table-column prop="serial_number" label="序列号" width="180" />
        <el-table-column label="状态" width="100">
          <template #default="{ row }">
            <ResultBadge :result="row.status" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180" />
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewDetail(row.test_id)">
              查看
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        v-model:current-page="filters.page"
        :page-size="filters.page_size"
        :total="total"
        layout="prev, pager, next"
        @current-change="search"
        style="margin-top: 16px; justify-content: center;"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import ResultBadge from '@/components/ResultBadge.vue'
import { testApi } from '@/api/test'
import { useTestStore } from '@/stores/test'

const router = useRouter()
const testStore = useTestStore()

const testTypes = ref<any[]>([])
const results = ref<any[]>([])
const total = ref(0)
const loading = ref(false)

const filters = reactive({
  serial_number: '',
  test_type: '',
  status: '',
  page: 1,
  page_size: 20,
})

onMounted(async () => {
  await testStore.fetchTypes()
  testTypes.value = testStore.testTypes
  search()
})

async function search() {
  loading.value = true
  try {
    const res: any = await testApi.getResults(filters)
    results.value = res.items || []
    total.value = res.total || 0
  } catch (e) {
  } finally {
    loading.value = false
  }
}

function viewDetail(testId: string) {
  router.push({ name: 'test-run', params: { id: testId } })
}
</script>

<style scoped>
.results-view {
  max-width: 1200px;
  margin: 0 auto;
}
.page-title {
  font-size: 24px;
  margin-bottom: 16px;
}
.filter-card {
  margin-bottom: 16px;
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
.table-card {
  background-color: var(--bg-card);
  border-color: var(--border-color);
}
</style>
