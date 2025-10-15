import { defineComponent, ref, computed, mergeProps, unref, useSSRContext } from 'vue';
import { ssrRenderAttrs, ssrIncludeBooleanAttr, ssrLooseEqual, ssrRenderAttr, ssrRenderClass, ssrInterpolate, ssrRenderStyle, ssrRenderList, ssrRenderTeleport } from 'vue/server-renderer';
import { b as useRuntimeConfig } from './server.mjs';
import '../nitro/nitro.mjs';
import 'node:http';
import 'node:https';
import 'node:events';
import 'node:buffer';
import 'node:fs';
import 'node:path';
import 'node:crypto';
import '../routes/renderer.mjs';
import 'vue-bundle-renderer/runtime';
import 'unhead/server';
import 'devalue';
import 'unhead/utils';
import 'unhead/plugins';
import 'vue-router';

const _sfc_main = /* @__PURE__ */ defineComponent({
  __name: "index",
  __ssrInlineRender: true,
  setup(__props) {
    const config = useRuntimeConfig();
    config.public.apiBase;
    const inputMode = ref("url");
    const urlInput = ref("");
    const selectedFile = ref(null);
    const isDragging = ref(false);
    const isProcessing = ref(false);
    ref(null);
    const jobStatus = ref(null);
    const progress = ref(0);
    const statusMessage = ref("\u5F85\u6A5F\u4E2D...");
    const segments = ref([]);
    const result = ref(null);
    const screenshotUrl = ref("");
    const showImageModal = ref(false);
    const isPreviewOpen = ref(true);
    const canSubmit = computed(() => {
      if (inputMode.value === "url") {
        return urlInput.value.trim() !== "";
      }
      return selectedFile.value !== null;
    });
    return (_ctx, _push, _parent, _attrs) => {
      _push(`<div${ssrRenderAttrs(mergeProps({ class: "min-h-screen bg-gray-50" }, _attrs))}><div class="max-w-7xl mx-auto px-4 py-8"><header class="mb-8"><h1 class="text-4xl font-bold text-gray-900 mb-2"> \u2728 LP\u6587\u5B57\u8D77\u3053\u3057\u30C4\u30FC\u30EB </h1><p class="text-lg text-gray-600"> URL\u3084\u30ED\u30FC\u30AB\u30EBHTML\u304B\u3089\u7C21\u5358\u306B\u6587\u5B57\u8D77\u3053\u3057 </p></header><div class="card mb-6"><h2 class="text-xl font-bold mb-4">\u{1F4DD} \u5165\u529B\u8A2D\u5B9A</h2><div class="mb-4"><div class="flex gap-6"><label class="flex items-center cursor-pointer"><input type="radio"${ssrIncludeBooleanAttr(ssrLooseEqual(unref(inputMode), "url")) ? " checked" : ""} value="url" class="mr-2"><span class="text-gray-700">\u{1F310} URL</span></label><label class="flex items-center cursor-pointer"><input type="radio"${ssrIncludeBooleanAttr(ssrLooseEqual(unref(inputMode), "upload")) ? " checked" : ""} value="upload" class="mr-2"><span class="text-gray-700">\u{1F4C1} \u30ED\u30FC\u30AB\u30EBHTML</span></label></div></div>`);
      if (unref(inputMode) === "url") {
        _push(`<div class="mb-4"><input${ssrRenderAttr("value", unref(urlInput))} type="url" placeholder="https://example.com" class="input-field"></div>`);
      } else {
        _push(`<div class="mb-4"><div class="${ssrRenderClass([
          "border-2 border-dashed rounded-lg p-6 text-center transition-colors",
          unref(isDragging) ? "border-primary bg-primary-light" : "border-gray-300 bg-gray-50"
        ])}"><input type="file" accept=".html,.htm" class="hidden">`);
        if (!unref(selectedFile)) {
          _push(`<div><p class="text-gray-600 mb-2 text-sm"> \u30D5\u30A1\u30A4\u30EB\u3092\u30C9\u30E9\u30C3\u30B0&amp;\u30C9\u30ED\u30C3\u30D7 \u307E\u305F\u306F </p><button class="btn-secondary text-sm"> \u{1F4C2} \u30D5\u30A1\u30A4\u30EB\u3092\u9078\u629E </button></div>`);
        } else {
          _push(`<div><p class="text-gray-700 font-semibold mb-2 text-sm">${ssrInterpolate(unref(selectedFile).name)}</p><button class="btn-secondary text-sm"> \u2715 \u524A\u9664 </button></div>`);
        }
        _push(`</div></div>`);
      }
      _push(`<button${ssrIncludeBooleanAttr(unref(isProcessing) || !unref(canSubmit)) ? " disabled" : ""} class="btn-primary w-full disabled:opacity-50 disabled:cursor-not-allowed">`);
      if (!unref(isProcessing)) {
        _push(`<span>\u{1F680} \u6587\u5B57\u8D77\u3053\u3057\u5B9F\u884C</span>`);
      } else {
        _push(`<span>\u51E6\u7406\u4E2D...</span>`);
      }
      _push(`</button></div>`);
      if (unref(isProcessing) || unref(jobStatus)) {
        _push(`<div class="card mb-6"><h2 class="text-xl font-bold mb-4">\u23F3 \u9032\u884C\u72B6\u6CC1</h2><div class="w-full bg-gray-200 rounded-full h-2 mb-3"><div class="bg-primary h-2 rounded-full transition-all duration-300" style="${ssrRenderStyle({ width: `${unref(progress)}%` })}"></div></div><p class="text-sm text-gray-600">${ssrInterpolate(unref(statusMessage))}</p></div>`);
      } else {
        _push(`<!---->`);
      }
      if (unref(segments).length > 0) {
        _push(`<div class="grid grid-cols-1 lg:grid-cols-2 gap-6"><div class="card"><button class="w-full flex items-center justify-between text-left mb-4"><h2 class="text-xl font-bold">\u{1F4F8} \u30B9\u30AF\u30EA\u30FC\u30F3\u30B7\u30E7\u30C3\u30C8\u30D7\u30EC\u30D3\u30E5\u30FC</h2><svg class="${ssrRenderClass(["w-6 h-6 transition-transform", unref(isPreviewOpen) ? "rotate-180" : ""])}" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path></svg></button><div class="transition-all duration-300" style="${ssrRenderStyle(unref(isPreviewOpen) ? null : { display: "none" })}"><div class="cursor-pointer hover:opacity-90 transition-opacity"><img${ssrRenderAttr("src", unref(screenshotUrl))} alt="Screenshot" class="w-full rounded-lg border border-gray-200 shadow-sm"><p class="text-xs text-center text-gray-500 mt-2"> \u30AF\u30EA\u30C3\u30AF\u3067\u62E1\u5927\u8868\u793A </p></div></div></div><div class="space-y-6"><div class="card"><h2 class="text-xl font-bold mb-4">\u{1F4C4} \u30B9\u30E9\u30A4\u30B9\u3054\u3068\u306E\u6587\u5B57\u8D77\u3053\u3057\u7D50\u679C</h2><div class="space-y-4 max-h-[600px] overflow-y-auto pr-2"><!--[-->`);
        ssrRenderList(unref(segments), (segment) => {
          _push(`<div class="border border-gray-200 rounded-lg p-4 bg-gray-50"><div class="flex items-center justify-between mb-2"><h3 class="font-semibold text-gray-800"> \u30B9\u30E9\u30A4\u30B9 #${ssrInterpolate(segment.index)}</h3><button class="text-xs text-primary hover:text-primary-hover"> \u{1F4CB} \u30B3\u30D4\u30FC </button></div><div class="text-xs text-gray-500 mb-2"> \u4F4D\u7F6E: ${ssrInterpolate(segment.top)}px \u301C ${ssrInterpolate(segment.bottom)}px </div><pre class="whitespace-pre-wrap text-sm text-gray-700">${ssrInterpolate(segment.text || "\uFF08\u30C6\u30AD\u30B9\u30C8\u306A\u3057\uFF09")}</pre></div>`);
        });
        _push(`<!--]--></div><button class="btn-primary w-full mt-4"> \u{1F4CB} \u5168\u30B9\u30E9\u30A4\u30B9\u3092\u30B3\u30D4\u30FC </button><div class="mt-4"><h3 class="text-sm font-semibold text-gray-700 mb-2"> \u{1F4BE} \u30C0\u30A6\u30F3\u30ED\u30FC\u30C9\u5F62\u5F0F\u3092\u9078\u629E </h3><div class="space-y-2"><button class="btn-secondary w-full justify-center"> \u{1F4C4} Markdown </button><button class="btn-secondary w-full justify-center"> \u{1F4C4} \u30C6\u30AD\u30B9\u30C8 </button><button class="btn-secondary w-full justify-center"> \u{1F4F8} \u30B9\u30AF\u30EA\u30FC\u30F3\u30B7\u30E7\u30C3\u30C8 </button></div></div>`);
        if (unref(result)) {
          _push(`<div class="mt-4 p-3 bg-gray-50 rounded text-xs text-gray-600"><p class="font-semibold mb-1">\u51FA\u529B\u5148:</p><p class="break-all">${ssrInterpolate(unref(result).run_dir)}</p></div>`);
        } else {
          _push(`<!---->`);
        }
        _push(`</div></div></div>`);
      } else {
        _push(`<!---->`);
      }
      _push(`</div>`);
      ssrRenderTeleport(_push, (_push2) => {
        if (unref(showImageModal)) {
          _push2(`<div class="fixed inset-0 bg-black bg-opacity-75 z-50 flex items-center justify-center p-4"><div class="relative max-w-6xl max-h-full overflow-auto"><button class="absolute top-4 right-4 bg-white rounded-full p-2 shadow-lg hover:bg-gray-100 transition-colors z-10"><svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg></button><img${ssrRenderAttr("src", unref(screenshotUrl))} alt="Screenshot" class="max-w-full max-h-full rounded-lg"></div></div>`);
        } else {
          _push2(`<!---->`);
        }
      }, "body", false, _parent);
      _push(`</div>`);
    };
  }
});
const _sfc_setup = _sfc_main.setup;
_sfc_main.setup = (props, ctx) => {
  const ssrContext = useSSRContext();
  (ssrContext.modules || (ssrContext.modules = /* @__PURE__ */ new Set())).add("pages/index.vue");
  return _sfc_setup ? _sfc_setup(props, ctx) : void 0;
};

export { _sfc_main as default };
//# sourceMappingURL=index-DrdHt3vU.mjs.map
