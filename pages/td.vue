<template>
  <div class="min-h-screen bg-gray-50">
    <div class="max-w-6xl mx-auto px-4 py-8 space-y-8">
      <header>
        <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 class="text-3xl font-bold text-gray-900">🚀 TD作成くん Webアプリ</h1>
            <p class="text-gray-600 mt-1">
              ターゲットと検索キーワードから検索広告・SEOの傾向を分析し、TD案を自動生成します。
            </p>
          </div>
          <NuxtLink
            to="/"
            class="inline-flex items-center text-sm text-primary hover:text-primary-hover transition"
          >
            ← LP文字起こしツールへ戻る
          </NuxtLink>
        </div>
      </header>

      <section class="card space-y-6">
        <div>
          <h2 class="text-xl font-semibold text-gray-900 mb-3">📝 入力情報</h2>
          <p class="text-sm text-gray-500">
            ScrapingDogのAPIキーを環境変数に設定したバックエンドが必要です。
          </p>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">ターゲット（必須）</label>
            <input
              v-model="target"
              type="text"
              placeholder="例: BtoBマーケ担当者 / 個人投資家 など"
              class="input-field"
            />
          </div>

          <div class="space-y-2">
            <label class="block text-sm font-medium text-gray-700">検索キーワード（必須）</label>
            <input
              v-model="keyword"
              type="text"
              placeholder="例: マーケティング オートメーション 比較"
              class="input-field"
            />
          </div>
        </div>

        <div class="space-y-2">
          <label class="block text-sm font-medium text-gray-700">
            配信予定サイトの特徴（任意）
          </label>
          <textarea
            v-model="siteInfo"
            rows="3"
            placeholder="例: 国産ツールでサポート重視 / 初月無料キャンペーン実施中"
            class="input-field resize-none"
          ></textarea>
        </div>

        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <button
            @click="runTdPipeline"
            :disabled="isLoading || !canSubmit"
            class="btn-primary w-full sm:w-auto disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="!isLoading">分析を実行する</span>
            <span v-else>処理中...</span>
          </button>
          <p class="text-xs text-gray-400">
            所要時間: 30秒前後（検索結果とサイト構成によって変動します）
          </p>
        </div>

        <p v-if="errorMessage" class="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md p-3">
          {{ errorMessage }}
        </p>
      </section>

      <section v-if="result" class="space-y-8">
        <div class="card">
          <h2 class="text-xl font-semibold text-gray-900 mb-4">🔍 検索意図の推定</h2>
          <p class="text-lg font-medium text-primary mb-2">
            メイン意図: {{ result.intent.primary }}
          </p>
          <details class="bg-gray-50 border border-gray-200 rounded-md p-4">
            <summary class="cursor-pointer text-sm text-gray-600 mb-2">
              根拠を見る
            </summary>
            <ul class="list-disc list-inside text-sm text-gray-600 space-y-1">
              <li v-for="(evidence, index) in result.intent.evidence" :key="index">
                {{ evidence }}
              </li>
            </ul>
          </details>
        </div>

        <div class="card">
          <h2 class="text-xl font-semibold text-gray-900 mb-4">🏁 提案TD（広告文）</h2>
          <div class="grid md:grid-cols-3 gap-4">
            <div
              v-for="(proposal, index) in result.proposals"
              :key="index"
              class="border border-gray-200 rounded-lg p-4 bg-gray-50"
            >
              <p class="text-xs text-gray-500 mb-1">案{{ index + 1 }}</p>
              <h3 class="font-semibold text-gray-800 mb-2">{{ proposal.title }}</h3>
              <p class="text-sm text-gray-700 whitespace-pre-line mb-2">
                {{ proposal.description }}
              </p>
              <p class="text-sm font-medium text-primary mb-3">{{ proposal.cta }}</p>
              <details class="text-xs text-gray-500">
                <summary class="cursor-pointer">根拠を見る</summary>
                <ul class="list-disc list-inside space-y-1 mt-1">
                  <li v-for="(line, rIndex) in proposal.rationale" :key="rIndex">
                    {{ line }}
                  </li>
                </ul>
              </details>
            </div>
          </div>
        </div>

        <div class="grid md:grid-cols-2 gap-6">
          <div class="card">
            <h2 class="text-xl font-semibold text-gray-900 mb-4">📣 訴求軸の分析</h2>
            <div v-if="result.appeal_axes.length" class="space-y-4">
              <div
                v-for="(axis, index) in result.appeal_axes"
                :key="index"
                class="border border-gray-200 rounded-lg p-4 bg-white"
              >
                <div class="flex items-center justify-between mb-2">
                  <span class="font-semibold text-gray-800">{{ axis.name }}</span>
                  <span class="text-sm text-primary">
                    スコア: {{ axis.score.toFixed(2) }}
                  </span>
                </div>
                <ul class="text-xs text-gray-500 space-y-1 list-disc list-inside">
                  <li v-for="(evidence, eIndex) in axis.evidence" :key="eIndex">
                    {{ evidence }}
                  </li>
                </ul>
              </div>
            </div>
            <p v-else class="text-sm text-gray-500">
              訴求軸に関する明確な分析結果が得られませんでした。
            </p>
          </div>

          <div class="card">
            <h2 class="text-xl font-semibold text-gray-900 mb-4">📄 SEO上位の要点</h2>
            <div class="space-y-4 max-h-[360px] overflow-y-auto pr-2">
              <div
                v-for="insight in result.seo_insights"
                :key="insight.position"
                class="border border-gray-200 rounded-lg p-4 bg-white"
              >
                <div class="flex items-center justify-between mb-1">
                  <span class="text-xs text-gray-400">#{{ insight.position }}</span>
                </div>
                <h3 class="font-semibold text-gray-800 mb-1">{{ insight.title }}</h3>
                <p class="text-sm text-gray-600 mb-2">{{ insight.summary }}</p>
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="(topic, index) in insight.key_topics"
                    :key="index"
                    class="inline-flex items-center px-2 py-1 rounded-full bg-primary-light text-primary text-xs"
                  >
                    {{ topic }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="card">
          <h2 class="text-xl font-semibold text-gray-900 mb-4">
            💡 スポンサード広告の抜粋
          </h2>
          <div v-if="result.ads.length" class="space-y-4">
            <div
              v-for="ad in result.ads"
              :key="ad.position"
              class="border border-gray-200 rounded-lg p-4 bg-white"
            >
              <div class="flex items-center justify-between text-sm text-gray-500 mb-1">
                <span>広告 #{{ ad.position }}</span>
                <span v-if="ad.display_link">{{ ad.display_link }}</span>
              </div>
              <h3 class="font-semibold text-gray-800 mb-1">{{ ad.title }}</h3>
              <p class="text-sm text-gray-600 mb-2 whitespace-pre-line">
                {{ ad.description || '説明文なし' }}
              </p>
              <a
                v-if="ad.link"
                :href="ad.link"
                target="_blank"
                rel="noopener noreferrer"
                class="text-xs text-primary hover:text-primary-hover"
              >
                リンクを開く →
              </a>
              <details v-if="ad.summary" class="mt-3 text-xs text-gray-500">
                <summary class="cursor-pointer">サイト要約を見る</summary>
                <div class="mt-2 space-y-1">
                  <p v-if="ad.summary.title" class="font-medium text-gray-700">
                    {{ ad.summary.title }}
                  </p>
                  <p v-if="ad.summary.meta_description">{{ ad.summary.meta_description }}</p>
                  <ul v-if="ad.summary.headings?.length" class="list-disc list-inside">
                    <li v-for="(heading, hIndex) in ad.summary.headings" :key="hIndex">
                      {{ heading }}
                    </li>
                  </ul>
                </div>
              </details>
            </div>
          </div>
          <p v-else class="text-sm text-gray-500">
            スポンサード広告は検出されませんでした。
          </p>
        </div>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
const config = useRuntimeConfig()
const apiBase = config.public.apiBase

const target = ref('')
const keyword = ref('')
const siteInfo = ref('')

const isLoading = ref(false)
const errorMessage = ref('')
const result = ref<any | null>(null)

useHead({
  title: 'TD作成くん Webアプリ',
  meta: [
    {
      name: 'description',
      content: '検索広告とSEOの傾向を収集・分析し、Google広告用のTD案を生成するツール'
    }
  ]
})

const canSubmit = computed(() => target.value.trim() !== '' && keyword.value.trim() !== '')

const runTdPipeline = async () => {
  if (!canSubmit.value || isLoading.value) return

  isLoading.value = true
  errorMessage.value = ''
  result.value = null

  try {
    const payload = {
      target: target.value.trim(),
      keyword: keyword.value.trim(),
      site_info: siteInfo.value.trim() || null
    }

    const data = await $fetch<any>(`${apiBase}/api/td/build`, {
      method: 'POST',
      body: payload
    })

    result.value = data
  } catch (error: any) {
    if (error?.data?.detail) {
      errorMessage.value = error.data.detail
    } else if (error?.message) {
      errorMessage.value = error.message
    } else {
      errorMessage.value = 'TD生成中にエラーが発生しました。時間を置いて再度お試しください。'
    }
  } finally {
    isLoading.value = false
  }
}
</script>
