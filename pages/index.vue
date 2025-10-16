<template>
  <div class="min-h-screen bg-gray-50">
    <div class="max-w-7xl mx-auto px-4 py-8">
      <!-- ヘッダー -->
      <header class="mb-8">
        <h1 class="text-4xl font-bold text-gray-900 mb-2">
          ✨ LP文字起こしツール
        </h1>
        <p class="text-lg text-gray-600">
          URLやローカルHTMLから簡単に文字起こし
        </p>
        <p class="text-sm text-primary mt-3">
          <NuxtLink to="/td" class="hover:text-primary-hover transition">
            👉 Google広告TDを自動生成する「TD作成くん Webアプリ」はこちら
          </NuxtLink>
        </p>
      </header>

      <!-- 入力セクション -->
      <div class="card mb-6">
        <h2 class="text-xl font-bold mb-4">📝 入力設定</h2>

        <!-- モード選択 -->
        <div class="mb-4">
          <div class="flex gap-6">
            <label class="flex items-center cursor-pointer">
              <input
                type="radio"
                v-model="inputMode"
                value="url"
                class="mr-2"
              />
              <span class="text-gray-700">🌐 URL</span>
            </label>
            <label class="flex items-center cursor-pointer">
              <input
                type="radio"
                v-model="inputMode"
                value="upload"
                class="mr-2"
              />
              <span class="text-gray-700">📁 ローカルHTML</span>
            </label>
          </div>
        </div>

        <!-- URL入力 -->
        <div v-if="inputMode === 'url'" class="mb-4">
          <input
            v-model="urlInput"
            type="url"
            placeholder="https://example.com"
            class="input-field"
          />
        </div>

        <!-- ファイルアップロード -->
        <div v-else class="mb-4">
          <div
            @drop.prevent="handleDrop"
            @dragover.prevent
            @dragenter="isDragging = true"
            @dragleave="isDragging = false"
            :class="[
              'border-2 border-dashed rounded-lg p-6 text-center transition-colors',
              isDragging
                ? 'border-primary bg-primary-light'
                : 'border-gray-300 bg-gray-50',
            ]"
          >
            <input
              ref="fileInput"
              type="file"
              accept=".html,.htm"
              @change="handleFileSelect"
              class="hidden"
            />
            <div v-if="!selectedFile">
              <p class="text-gray-600 mb-2 text-sm">
                ファイルをドラッグ&ドロップ または
              </p>
              <button
                @click="$refs.fileInput.click()"
                class="btn-secondary text-sm"
              >
                📂 ファイルを選択
              </button>
            </div>
            <div v-else>
              <p class="text-gray-700 font-semibold mb-2 text-sm">
                {{ selectedFile.name }}
              </p>
              <button @click="selectedFile = null" class="btn-secondary text-sm">
                ✕ 削除
              </button>
            </div>
          </div>
        </div>

        <!-- 実行ボタン -->
        <button
          @click="startTranscription"
          :disabled="isProcessing || !canSubmit"
          class="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span v-if="!isProcessing">🚀 文字起こし実行</span>
          <span v-else>処理中...</span>
        </button>
      </div>

      <!-- 進行状況 -->
      <div v-if="isProcessing || jobStatus" class="card mb-6">
        <h2 class="text-xl font-bold mb-4">⏳ 進行状況</h2>
        <div class="w-full bg-gray-200 rounded-full h-2 mb-3">
          <div
            class="bg-primary h-2 rounded-full transition-all duration-300"
            :style="{ width: `${progress}%` }"
          ></div>
        </div>
        <p class="text-sm text-gray-600 mb-4">{{ statusMessage }}</p>

        <!-- ログ表示 -->
        <div v-if="logs.length > 0" class="mt-4">
          <h3 class="text-sm font-semibold text-gray-700 mb-2">📋 処理ログ</h3>
          <div class="bg-gray-50 rounded-lg p-3 max-h-48 overflow-y-auto">
            <div
              v-for="(log, index) in logs"
              :key="index"
              class="text-xs text-gray-600 mb-1 font-mono"
            >
              <span class="text-gray-400">{{ formatTime(log.timestamp) }}</span>
              <span class="ml-2">{{ log.message }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 結果表示エリア -->
      <div v-if="segments.length > 0" class="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <!-- 左カラム: スクリーンショットプレビュー（アコーディオン） -->
        <div class="card">
          <button
            @click="isPreviewOpen = !isPreviewOpen"
            class="w-full flex items-center justify-between text-left mb-4"
          >
            <h2 class="text-xl font-bold">📸 スクリーンショットプレビュー</h2>
            <svg
              :class="['w-6 h-6 transition-transform', isPreviewOpen ? 'rotate-180' : '']"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7" />
            </svg>
          </button>

          <div
            v-show="isPreviewOpen"
            class="transition-all duration-300"
          >
            <div
              @click="showImageModal = true"
              class="cursor-pointer hover:opacity-90 transition-opacity"
            >
              <img
                :src="screenshotUrl"
                alt="Screenshot"
                class="w-full rounded-lg border border-gray-200 shadow-sm"
              />
              <p class="text-xs text-center text-gray-500 mt-2">
                クリックで拡大表示
              </p>
            </div>
          </div>
        </div>

        <!-- 右カラム: セグメントごとの文字起こし結果 -->
        <div class="space-y-6">
          <!-- セグメントごとの文字起こし -->
          <div class="card">
            <h2 class="text-xl font-bold mb-4">📄 スライスごとの文字起こし結果</h2>

            <div class="space-y-4 max-h-[600px] overflow-y-auto pr-2">
              <div
                v-for="segment in segments"
                :key="segment.index"
                class="border border-gray-200 rounded-lg p-4 bg-gray-50"
              >
                <div class="flex items-center justify-between mb-2">
                  <h3 class="font-semibold text-gray-800">
                    スライス #{{ segment.index }}
                  </h3>
                  <button
                    @click="copySegment(segment)"
                    class="text-xs text-primary hover:text-primary-hover"
                  >
                    📋 コピー
                  </button>
                </div>
                <div class="text-xs text-gray-500 mb-2">
                  位置: {{ segment.top }}px 〜 {{ segment.bottom }}px
                </div>
                <pre class="whitespace-pre-wrap text-sm text-gray-700">{{
                  segment.text || '（テキストなし）'
                }}</pre>
              </div>
            </div>

            <!-- 全体コピーボタン -->
            <button
              @click="copyAllSegments"
              class="btn-primary w-full mt-4"
            >
              📋 全スライスをコピー
            </button>

            <!-- ダウンロード形式選択 -->
            <div class="mt-4">
              <h3 class="text-sm font-semibold text-gray-700 mb-2">
                💾 ダウンロード形式を選択
              </h3>
              <div class="space-y-2">
                <button
                  @click="downloadFile('markdown')"
                  class="btn-secondary w-full justify-center"
                >
                  📄 Markdown
                </button>
                <button
                  @click="downloadFile('text')"
                  class="btn-secondary w-full justify-center"
                >
                  📄 テキスト
                </button>
                <button
                  @click="downloadFile('screenshot')"
                  class="btn-secondary w-full justify-center"
                >
                  📸 スクリーンショット
                </button>
              </div>
            </div>

            <!-- 出力先 -->
            <div v-if="result" class="mt-4 p-3 bg-gray-50 rounded text-xs text-gray-600">
              <p class="font-semibold mb-1">出力先:</p>
              <p class="break-all">{{ result.run_dir }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 画像拡大モーダル -->
    <Teleport to="body">
      <div
        v-if="showImageModal"
        @click="showImageModal = false"
        class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"
      >
        <div class="relative max-w-6xl max-h-full overflow-auto">
          <button
            @click="showImageModal = false"
            class="absolute top-4 right-4 bg-white rounded-full p-2 shadow-lg hover:bg-gray-100 transition-colors z-10"
          >
            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
          <img
            :src="screenshotUrl"
            alt="Screenshot"
            class="max-w-full max-h-full rounded-lg"
            @click.stop
          />
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const inputMode = ref('url')
const urlInput = ref('')
const selectedFile = ref<File | null>(null)
const isDragging = ref(false)

const isProcessing = ref(false)
const jobId = ref<string | null>(null)
const jobStatus = ref<any>(null)
const progress = ref(0)
const statusMessage = ref('待機中...')
const segments = ref<Array<any>>([])
const result = ref<any>(null)
const screenshotUrl = ref('')
const showImageModal = ref(false)
const isPreviewOpen = ref(true)
const logs = ref<Array<{timestamp: string, message: string}>>([])

const canSubmit = computed(() => {
  if (inputMode.value === 'url') {
    return urlInput.value.trim() !== ''
  }
  return selectedFile.value !== null
})

const handleFileSelect = (event: Event) => {
  const target = event.target as HTMLInputElement
  if (target.files && target.files[0]) {
    selectedFile.value = target.files[0]
  }
}

const handleDrop = (event: DragEvent) => {
  isDragging.value = false
  if (event.dataTransfer?.files && event.dataTransfer.files[0]) {
    selectedFile.value = event.dataTransfer.files[0]
  }
}

const startTranscription = async () => {
  isProcessing.value = true
  progress.value = 0
  statusMessage.value = '処理を開始しています...'
  segments.value = []
  result.value = null
  screenshotUrl.value = ''
  logs.value = []

  try {
    let response

    if (inputMode.value === 'url') {
      // URL処理
      response = await fetch(`${apiBase}/api/transcribe/url`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ url: urlInput.value }),
      })
    } else {
      // ファイルアップロード
      const formData = new FormData()
      formData.append('file', selectedFile.value!)

      response = await fetch(`${apiBase}/api/transcribe/upload`, {
        method: 'POST',
        body: formData,
      })
    }

    if (!response.ok) {
      throw new Error('処理の開始に失敗しました')
    }

    const data = await response.json()
    jobId.value = data.job_id

    // ステータスをポーリング
    pollStatus()
  } catch (error) {
    console.error('Error:', error)
    statusMessage.value = 'エラーが発生しました'
    isProcessing.value = false
    alert('エラーが発生しました。もう一度お試しください。')
  }
}

const pollStatus = async () => {
  if (!jobId.value) return

  try {
    const response = await fetch(`${apiBase}/api/status/${jobId.value}`)
    if (!response.ok) throw new Error('Status check failed')

    const data = await response.json()
    jobStatus.value = data
    progress.value = data.progress || 0
    statusMessage.value = data.message || '処理中...'

    // ログを更新
    if (data.logs && data.logs.length > 0) {
      logs.value = data.logs
    }

    if (data.status === 'completed') {
      isProcessing.value = false
      result.value = data.result
      segments.value = data.result.segments || []

      // スクリーンショットURLを設定
      screenshotUrl.value = `${apiBase}/api/download/${jobId.value}/screenshot`

      statusMessage.value = '完了！'
    } else if (data.status === 'error') {
      isProcessing.value = false
      statusMessage.value = `エラー: ${data.error}`
      alert(`エラーが発生しました: ${data.error}`)
    } else {
      // 処理中の場合は1秒後に再度ポーリング
      setTimeout(pollStatus, 1000)
    }
  } catch (error) {
    console.error('Polling error:', error)
    isProcessing.value = false
    statusMessage.value = 'ステータス確認エラー'
  }
}

const copySegment = (segment: any) => {
  if (!segment.text) {
    alert('コピーする内容がありません')
    return
  }
  navigator.clipboard.writeText(segment.text)
  alert(`📋 スライス #${segment.index} をコピーしました！`)
}

const copyAllSegments = () => {
  if (segments.value.length === 0) {
    alert('コピーする内容がありません')
    return
  }
  const allText = segments.value
    .map(seg => `# スライス ${seg.index}\n\n${seg.text}`)
    .join('\n\n---\n\n')
  navigator.clipboard.writeText(allText)
  alert('📋 全スライスをクリップボードにコピーしました！')
}

const downloadFile = (fileType: string) => {
  if (!jobId.value) return
  const url = `${apiBase}/api/download/${jobId.value}/${fileType}`
  window.open(url, '_blank')
}

const formatTime = (timestamp: string) => {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('ja-JP', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}
</script>
