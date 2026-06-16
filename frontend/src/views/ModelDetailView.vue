<template>
  <AppLayout>
    <div class="model-detail">
      <!-- 顶部导航栏 -->
      <div class="model-header">
        <div class="header-left">
          <el-button text @click="router.push('/project')">
            <el-icon><ArrowLeft /></el-icon>
            返回
          </el-button>
          <h2 class="model-title">{{ model.name }}</h2>
          <el-tag size="small" :type="dataStatusType">{{ dataStatusText }}</el-tag>
          <el-tag size="small" :type="trainingStatusType">{{ trainingStatusText }}</el-tag>
          <el-tag size="small" :type="testStatusType">{{ testStatusText }}</el-tag>
        </div>
        <div class="header-desc">{{ model.description || "暂无描述" }}</div>
      </div>

      <!-- 三资源区域 -->
      <div class="resource-grid">
        <!-- 良品数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            良品数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'good'"
                @click="showZipUpload('good')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'good'"
                :disabled="!goodLoaded"
                @click="download('good')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!goodLoaded"
                :loading="isLoading('delete-good')"
                @click="confirmDelete('good')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!goodLoaded"
                @click="annotate('good')"
                >标注</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!goodLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag
                  v-if="Object.keys(goodErrors).length === 0"
                  type="success"
                  size="small"
                >
                  成功 {{ goodPassed }} 张
                </el-tag>
                <el-button
                  v-else
                  type="warning"
                  size="small"
                  text
                  @click="showErrors('good')"
                >
                  问题 ({{ goodFailed }})
                </el-button>
              </template>
            </div>
          </div>
        </div>

        <!-- 缺陷数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            缺陷数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'defect'"
                @click="showZipUpload('defect')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'defect'"
                :disabled="!defectLoaded"
                @click="download('defect')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!defectLoaded"
                :loading="isLoading('delete-defect')"
                @click="confirmDelete('defect')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!defectLoaded"
                @click="annotate('defect')"
                >标注</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!defectLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag
                  v-if="Object.keys(defectErrors).length === 0"
                  type="success"
                  size="small"
                >
                  成功 {{ defectPassed }} 张
                </el-tag>
                <el-button
                  v-else
                  type="warning"
                  size="small"
                  text
                  @click="showErrors('defect')"
                >
                  问题 ({{ defectFailed }})
                </el-button>
              </template>
            </div>
          </div>
        </div>

        <!-- 模型参数 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Document /></el-icon>
            模型参数
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button size="small" @click="showJsonUpload"
                >上传 JSON</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'parameter'"
                :disabled="!paramLoaded"
                @click="download('parameter')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!paramLoaded"
                :loading="isLoading('delete-parameter')"
                @click="confirmDelete('parameter')"
                >删除</el-button
              >
              <el-button size="small" type="primary" class="btn-solid" :loading="isLoading('open-param')" @click="openParamEditor">编辑</el-button>
            </div>
            <div class="resource-status">
              <span v-if="!paramLoaded" class="empty-text">暂无数据</span>
              <el-tag v-else type="success" size="small">已上传</el-tag>
            </div>
          </div>
        </div>

        <!-- 测试数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            测试数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'test'"
                @click="showZipUpload('test')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'test'"
                :disabled="!testLoaded"
                @click="download('test')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!testLoaded"
                :loading="isLoading('delete-test')"
                @click="confirmDelete('test')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!testLoaded"
                @click="annotate('test')"
                >预览</el-button
              >
              <el-button
                size="small"
                :loading="isLoading('test-logs')"
                :disabled="!testLoaded"
                @click="handleTestLogs"
                >测试日志</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!testLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag type="success" size="small">成功 {{ testPassed }} 张</el-tag>
              </template>
            </div>
          </div>
        </div>

        <!-- 模板数据库 -->
        <div class="resource-section">
          <h3 class="resource-title">
            <el-icon><Folder /></el-icon>
            模板数据库
          </h3>
          <div class="resource-body">
            <div class="resource-actions">
              <el-button
                size="small"
                :loading="uploading === 'template'"
                @click="showZipUpload('template')"
                >上传 ZIP</el-button
              >
              <el-button
                size="small"
                :loading="downloading === 'template'"
                :disabled="!templateLoaded"
                @click="download('template')"
                >下载</el-button
              >
              <el-button
                size="small"
                type="danger"
                :disabled="!templateLoaded"
                :loading="isLoading('delete-template')"
                @click="confirmDelete('template')"
                >删除</el-button
              >
              <el-button
                size="small"
                type="primary"
                :disabled="!templateLoaded"
                @click="annotate('template')"
                >预览</el-button
              >
            </div>
            <div class="resource-status">
              <span v-if="!templateLoaded" class="empty-text">暂无数据</span>
              <template v-else>
                <el-tag type="success" size="small">成功 {{ templatePassed }} 张</el-tag>
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- ZIP 上传弹窗 -->
      <el-dialog
        v-model="showZipDialog"
        :title="zipDialogTitle"
        width="500px"
      >
        <ZipUpload
          :model-id="modelId"
          :type="zipType"
          @uploaded="handleZipUploaded"
          @all-uploaded="handleZipAllUploaded"
        />
      </el-dialog>

      <!-- JSON 上传弹窗 -->
      <el-dialog v-model="showJsonDialog" title="上传模型参数" width="400px">
        <JsonUpload :model-id="modelId" @uploaded="handleJsonUploaded" />
      </el-dialog>

      <!-- JSON 编辑器 -->
      <JsonEditor
        v-model="showParamEditor"
        title="编辑模型参数"
        :initial-content="paramEditorContent"
        @save="handleParamSave"
      />

      <!-- 错误详情弹窗 -->
      <el-dialog v-model="showErrorDialog" title="错误详情" width="600px">
        <el-table :data="sortedErrors" size="small" max-height="400">
          <el-table-column prop="path" label="图片路径" />
          <el-table-column prop="type" label="错误类型" width="140" />
          <el-table-column prop="message" label="错误信息" />
        </el-table>
      </el-dialog>

      <!-- 测试日志弹窗 -->
      <el-dialog v-model="showTestLogsDialog" title="测试日志" width="700px">
        <pre class="logs-content">{{ testLogsContent || '暂无日志' }}</pre>
      </el-dialog>

      <DownloadDialog ref="downloadDialogRef" />
    </div>
  </AppLayout>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage, ElMessageBox } from "element-plus";
import { ArrowLeft, Folder, Document } from "@element-plus/icons-vue";
import AppLayout from "../components/Layout/AppLayout.vue";
import ZipUpload from "../components/Upload/ZipUpload.vue";
import JsonUpload from "../components/Upload/JsonUpload.vue";
import JsonEditor from "../components/Editor/JsonEditor.vue";
import DownloadDialog from "../components/Download/DownloadDialog.vue";
import { useSingleLoading } from "../composables/useDelayedLoading";
import { useProjectStore } from "../stores/project";
import { resolveDataStatus, dataStatusTagType, dataStatusDisplayText, resolveTrainingStatus, trainingStatusTagType, trainingStatusDisplayText, resolveTestStatus, testStatusTagType, testStatusDisplayText } from "../utils/model-status";
import { getModel } from "../api/model";
import {
  deleteGood,
  deleteDefect,
  deleteParameter,
  deleteTest,
  deleteTemplate,
  downloadParameter,
  getParameter,
  editParameter,
  deleteParameterFile,
  checkDiskSpace,
} from "../api/resource";

const route = useRoute();
const router = useRouter();
const store = useProjectStore();

const modelId = computed(() => route.params.modelId as string);

// 模型信息
const model = ref({
  id: "",
  name: "",
  description: "",
  status: {
    file_status: { status: "idle" },
    training_status: { status: "idle" },
    test_status: { status: "idle" },
  },
  packages: [] as any[],
});

const { loadingAction, startLoading, stopLoading, isLoading } = useSingleLoading();

const dataStatusType = computed(() => dataStatusTagType(resolveDataStatus(model.value.status)))
const dataStatusText = computed(() => dataStatusDisplayText(resolveDataStatus(model.value.status)))
const trainingStatusType = computed(() => trainingStatusTagType(resolveTrainingStatus(model.value.status)))
const trainingStatusText = computed(() => trainingStatusDisplayText(resolveTrainingStatus(model.value.status)))
const testStatusType = computed(() => testStatusTagType(resolveTestStatus(model.value.status)))
const testStatusText = computed(() => testStatusDisplayText(resolveTestStatus(model.value.status)))
const zipDialogTitle = computed(() => {
  const titles: Record<string, string> = { good: '上传良品数据包', defect: '上传缺陷数据包', test: '上传测试数据包', template: '上传模板数据包' }
  return titles[zipType.value] || '上传数据包'
})

// 资源状态
const goodLoaded = ref(false);
const goodPassed = ref(0);
const goodFailed = ref(0);
const goodErrors = ref<any>({});

const defectLoaded = ref(false);
const defectPassed = ref(0);
const defectFailed = ref(0);
const defectErrors = ref<any>({});

const paramLoaded = ref(false);

const testLoaded = ref(false);
const testPassed = ref(0);
const testFailed = ref(0);
const testErrors = ref<any[]>([]);

const templateLoaded = ref(false);
const templatePassed = ref(0);
const templateFailed = ref(0);
const templateErrors = ref<any[]>([]);

// 上传状态
const uploading = ref<"good" | "defect" | "test" | "template" | null>(null);
const downloading = ref<"good" | "defect" | "parameter" | "test" | "template" | null>(null);
const downloadDialogRef = ref<InstanceType<typeof DownloadDialog>>();

// 弹窗控制
const showZipDialog = ref(false);
const zipType = ref<"good" | "defect" | "test" | "template">("good");
const showJsonDialog = ref(false);

// 参数编辑器
const showParamEditor = ref(false);
const paramEditorContent = ref("");

// 错误弹窗
const showErrorDialog = ref(false);
const currentErrors = ref<any[]>([]);
const sortedErrors = computed(() => {
  return [...currentErrors.value].sort((a, b) => (a.path || '').localeCompare(b.path || ''));
});

function showErrors(type: "good" | "defect" | "test" | "template") {
  const errorDicts: Record<string, any> = { good: goodErrors.value, defect: defectErrors.value, test: testErrors.value, template: templateErrors.value };
  const dict = errorDicts[type] || {};
  currentErrors.value = Object.entries(dict).map(([path, entry]: [string, any]) => ({ path, type: entry.type || 'error', message: entry.message, level: entry.level }));
  showErrorDialog.value = true;
}

// 测试日志
const showTestLogsDialog = ref(false)
const testLogsContent = ref('')

async function handleTestLogs() {
  startLoading('test-logs')
  try {
    const res = await store.getTestLogs(modelId.value)
    testLogsContent.value = res.log
    showTestLogsDialog.value = true
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '获取测试日志失败')
  } finally {
    stopLoading()
  }
}

// 加载模型详情（先清零再填充）
async function fetchModel() {
  try {
    const res = await getModel(modelId.value);
    model.value = res.data;
    const pkgs = res.data.packages || [];

    // 清零
    goodLoaded.value = false;
    goodPassed.value = 0;
    goodFailed.value = 0;
    goodErrors.value = {};
    defectLoaded.value = false;
    defectPassed.value = 0;
    defectFailed.value = 0;
    defectErrors.value = {};
    paramLoaded.value = false;
    testLoaded.value = false;
    testPassed.value = 0;
    testFailed.value = 0;
    testErrors.value = {};
    templateLoaded.value = false;
    templatePassed.value = 0;
    templateFailed.value = 0;
    templateErrors.value = {};

    // 填充
    const good = pkgs.find((p: any) => p.resource_type === "good");
    const defect = pkgs.find((p: any) => p.resource_type === "defect");
    const param = pkgs.find((p: any) => p.resource_type === "parameter");
    const test = pkgs.find((p: any) => p.resource_type === "test");
    const template = pkgs.find((p: any) => p.resource_type === "template");

    if (good) {
      goodLoaded.value = true;
      goodPassed.value = good.passed_count || 0;
      goodFailed.value = good.failed_count || 0;
      goodErrors.value = good.errors || {};
    }
    if (defect) {
      defectLoaded.value = true;
      defectPassed.value = defect.passed_count || 0;
      defectFailed.value = defect.failed_count || 0;
      defectErrors.value = defect.errors || {};
    }
    if (param) {
      paramLoaded.value = true;
    }
    if (test) {
      testLoaded.value = true;
      testPassed.value = test.passed_count || 0;
      testFailed.value = test.failed_count || 0;
      testErrors.value = test.errors || {};
    }
    if (template) {
      templateLoaded.value = true;
      templatePassed.value = template.passed_count || 0;
      templateFailed.value = template.failed_count || 0;
      templateErrors.value = template.errors || {};
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "加载模型失败");
  }
}

// ZIP 上传
async function showZipUpload(type: "good" | "defect" | "test" | "template") {
  let freeGb: number
  try {
    const res: any = await checkDiskSpace(modelId.value, type)
    freeGb = res.data.free_gb
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "磁盘检查失败")
    return
  }
  if (freeGb < 2) {
    ElMessage.warning("剩余空间不足2GB，请联系管理员")
    return
  }
  zipType.value = type
  showZipDialog.value = true
}

function handleZipUploaded(result: any) {
  uploading.value = null;
  if (result) {
    const updates: Record<string, any> = {
      good: { loaded: goodLoaded, passed: goodPassed, failed: goodFailed, errors: goodErrors },
      defect: { loaded: defectLoaded, passed: defectPassed, failed: defectFailed, errors: defectErrors },
      test: { loaded: testLoaded, passed: testPassed, failed: testFailed, errors: testErrors },
      template: { loaded: templateLoaded, passed: templatePassed, failed: templateFailed, errors: templateErrors },
    }
    const u = updates[zipType.value]
    if (u) {
      u.loaded.value = true;
      u.passed.value += result.passed_count || 0;
      u.failed.value += result.failed_count || 0;
      // Merge errors dict
      if (result.errors) {
        u.errors.value = { ...u.errors.value, ...result.errors };
      }
      // Merge msgs dict
      if (result.msgs) {
        // Not stored locally, but tree will reload on next loadModel call
      }
    }
  }
}

function handleZipAllUploaded() {
  showZipDialog.value = false;
  fetchModel();
}

// JSON 上传
function showJsonUpload() {
  showJsonDialog.value = true;
}

function handleJsonUploaded() {
  showJsonDialog.value = false;
  fetchModel();
}

// 下载
async function download(type: "good" | "defect" | "parameter" | "test" | "template") {
  if (!getTypeLoaded(type)) {
    ElMessage.warning("暂无数据");
    return;
  }
  const filenames: Record<string, string> = {
    good: "good.zip",
    defect: "defect.zip",
    parameter: "parameter.json",
    test: "test.zip",
    template: "template.zip",
  };

  // JSON 参数直接下载
  if (type === "parameter") {
    downloading.value = type;
    try {
      const res = await downloadParameter(modelId.value);
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement("a");
      a.href = url;
      a.download = filenames[type];
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      document.body.removeChild(a);
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || "下载失败");
    } finally {
      downloading.value = null;
    }
    return;
  }

  // ZIP 分片下载
  downloading.value = type;
  const { downloadInit, downloadChunk, downloadCleanup } = await import('../api/resource');
  try {
    const initRes = await downloadInit(modelId.value, type);
    downloadDialogRef.value?.openDownloadWithSession(
      {
        modelId: modelId.value,
        resourceType: type,
        filename: filenames[type],
        api: {
          init: () => Promise.resolve(),
          chunk: (mid: string, rt: string, sid: string, idx: number, signal?: AbortSignal) => downloadChunk(mid, rt, sid, idx, signal),
          cleanup: (mid: string, rt: string, sid: string) => downloadCleanup(mid, rt, sid),
        },
      },
      initRes.data,
    );
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "下载失败");
  } finally {
    downloading.value = null;
  }
}

// 删除
async function confirmDelete(type: "good" | "defect" | "parameter" | "test" | "template") {
  const labels: Record<string, string> = {
    good: "良品数据库",
    defect: "缺陷数据库",
    parameter: "模型参数",
    test: "测试数据库",
    template: "模板数据库",
  };
  try {
    await ElMessageBox.confirm(
      `确定删除${labels[type]}？此操作不可撤销。`,
      "确认删除",
      { type: "warning" },
    );
  } catch {
    return;
  }

  startLoading('delete-' + type)
  try {
    if (type === "good") await deleteGood(modelId.value);
    else if (type === "defect") await deleteDefect(modelId.value);
    else if (type === "test") await deleteTest(modelId.value);
    else if (type === "template") await deleteTemplate(modelId.value);
    else await deleteParameter(modelId.value);
    ElMessage.success("删除成功");
    fetchModel();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  } finally {
    stopLoading()
  }
}

// 参数编辑器
async function openParamEditor() {
  startLoading('open-param')
  paramEditorContent.value = "";
  try {
    const res = await getParameter(modelId.value);
    paramEditorContent.value = JSON.stringify(res.data.data, null, 2);
  } catch {
    // 文件不存在，空编辑
  } finally {
    stopLoading()
  }
  showParamEditor.value = true;
}

async function handleParamSave(content: string) {
  showParamEditor.value = false;
  if (!content.trim()) {
    // 空内容 = 删除文件
    startLoading('save-param')
    try {
      await deleteParameterFile(modelId.value);
      ElMessage.success("模型参数已删除");
      fetchModel();
    } catch (e: any) {
      ElMessage.error(e.response?.data?.detail || "删除失败");
    } finally {
      stopLoading()
    }
    return;
  }
  startLoading('save-param')
  try {
    const parsed = JSON.parse(content);
    await editParameter(modelId.value, parsed);
    ElMessage.success("模型参数已保存");
    fetchModel();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  } finally {
    stopLoading()
  }
}

// 标注/预览
async function annotate(type: string) {
  if (type === 'test') {
    const testStatus = resolveTestStatus(model.value.status)
    if (testStatus === 'success') {
      ElMessage.success('测试已成功，加载对应JSON标注')
    } else {
      ElMessage.warning('测试未完成，标注数据可能为空')
    }
    router.push(`/preview/${modelId.value}?type=${type}`)
  } else if (type === 'template') {
    router.push(`/preview/${modelId.value}?type=${type}`)
  } else {
    router.push(`/annotate/${modelId.value}?type=${type}`)
  }
}

function getTypeLoaded(type: string): boolean {
  if (type === "good") return goodLoaded.value;
  if (type === "defect") return defectLoaded.value;
  if (type === "parameter") return paramLoaded.value;
  if (type === "test") return testLoaded.value;
  if (type === "template") return templateLoaded.value;
  return false;
}

onMounted(() => {
  fetchModel();
});
</script>

<style scoped lang="scss">
.model-detail {
  max-width: 960px;
  margin: 0 auto;
  padding: var(--spacing-lg);
}

.model-header {
  margin-bottom: var(--spacing-xl);
  padding-bottom: var(--spacing-md);
  border-bottom: 1px solid var(--border-light);
}

.header-left {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  margin-bottom: var(--spacing-sm);
}

.model-title {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
}

.header-desc {
  color: var(--text-secondary);
  font-size: 14px;
  margin-left: calc(28px + var(--spacing-sm) * 2);
}

.resource-grid {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.resource-section {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--spacing-md) var(--spacing-lg);
  box-shadow: var(--shadow-sm);
}

.resource-title {
  margin: 0 0 var(--spacing-sm);
  font-size: 15px;
  font-weight: 600;
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);

  .el-icon {
    font-size: 18px;
    color: var(--color-primary);
  }
}

.resource-body {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.resource-actions {
  display: flex;
  gap: var(--spacing-sm);
}

.resource-status {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.empty-text {
  color: var(--text-secondary);
  font-size: 13px;
}

.resource-actions .btn-solid {
  color: #fff !important;

  &.is-loading,
  &.is-disabled {
    color: #fff !important;

    .el-button__text {
      color: #fff !important;
    }
  }
}

.logs-content {
  background: var(--bg-page);
  color: var(--text-primary);
  padding: var(--spacing-md);
  border-radius: var(--radius-sm);
  font-size: 13px;
  line-height: 1.5;
  max-height: 400px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}
</style>
