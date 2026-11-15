"""Expose AMD's pinned 3.1.6 analytical provider; keep legacy and FSR 4 choices."""
from pathlib import Path
from engine_stability import replace_once

CHANGES = [('gpu/vk/vk_fsr4.cpp',
  'std::atomic<int> g_why{-1};',
  'std::atomic<int> g_why{-1};\nstd::atomic<int> g_316_why{-1}; // independent provider availability'),
 ('gpu/vk/vk_fsr4.cpp',
  '\n#ifdef HOOKSHOT_FSR\n\nnamespace {',
  '\n'
  'FsrWhy fsr316_why() {\n'
  '    if (!fsr4_built()) return FSR_NOT_BUILT;\n'
  '    static const bool env_off = env_switch("RX_VK_FSR316") == 0;\n'
  '    if (env_off) return FSR_ENV_OFF;\n'
  '    const int w = g_316_why.load(std::memory_order_relaxed);\n'
  '    return w < 0 ? FSR_OK : (FsrWhy)w;\n'
  '}\n'
  '\n'
  '#ifdef HOOKSHOT_FSR\n'
  '\n'
  'namespace {'),
 ('gpu/vk/vk_fsr4.cpp', '    uint64_t version_id = 0;', '    uint64_t version_id = 0, version316_id = 0;'),
 ('gpu/vk/vk_fsr4.cpp', 'State& st() {', 'template<bool Fsr316> State& st() {'),
 ('gpu/vk/vk_fsr4.cpp',
  'void on_message(uint32_t type, const wchar_t* message) {',
  'template<bool Fsr316> void on_message(uint32_t type, const wchar_t* message) {'),
 ('gpu/vk/vk_fsr4.cpp',
  'logf("vk: AMD FSR 4: AMD\'s %s: %s", type == FFX_API_MESSAGE_TYPE_ERROR ? "error" : "warning", text);',
  'logf("vk: AMD FSR %s: AMD\'s %s: %s", Fsr316 ? "3.1.6" : "4", type == FFX_API_MESSAGE_TYPE_ERROR ? '
  '"error" : "warning", text);'),
 ('gpu/vk/vk_fsr4.cpp',
  '        g_why = why;\n        return false;',
  '        g_why = why;\n        g_316_why = why;\n        return false;'),
 ('gpu/vk/vk_fsr4.cpp',
  '        sscanf(name, "%u.%u.%u", &v[0], &v[1], &v[2]);',
  '        sscanf(name, "%u.%u.%u", &v[0], &v[1], &v[2]);\n'
  '        // Pin the requested analytical provider. Never substitute 4.x or another 3.x.\n'
  '        if (!strcmp(name, "3.1.6") && !l.version316_id) l.version316_id = ids[i];'),
 ('gpu/vk/vk_fsr4.cpp',
  '    if (!l.version_id) {\n'
  '        logf("vk: AMD FSR 4: no FSR 4 for this GPU (AMD\'s library has: %s)", listed.c_str());\n'
  '        return no(FSR_NO_MODEL);\n'
  '    }\n'
  '    logf("vk: AMD FSR 4: upscalers %s; using %u.%u.%u", listed.c_str(), best[0], best[1], best[2]);\n'
  '    l.ok = true;\n'
  '    g_why = FSR_OK;\n'
  '    return true;',
  '    g_why = l.version_id ? FSR_OK : FSR_NO_MODEL;\n'
  '    g_316_why = l.version316_id ? FSR_OK : FSR_NO_MODEL;\n'
  '    if (l.version_id)\n'
  '        logf("vk: AMD FSR 4: upscalers %s; using %u.%u.%u", listed.c_str(), best[0], best[1], best[2]);\n'
  '    else logf("vk: AMD FSR 4: no FSR 4 for this GPU (AMD\'s library has: %s)", listed.c_str());\n'
  '    logf("vk: AMD FSR 3.1.6: %s (AMD\'s library has: %s)", l.version316_id ? "available" : "unavailable", '
  'listed.c_str());\n'
  '    l.ok = l.version_id || l.version316_id;\n'
  '    return l.ok;'),
 ('gpu/vk/vk_fsr4.cpp',
  'std::shared_ptr<Context> make_context(uint32_t w, uint32_t h, bool hdr) {\n'
  '    Library& l = lib();\n'
  '    auto c = std::make_shared<Context>();\n'
  '    c->backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK;\n'
  '    c->backend.deviceContext = l.device_context;\n'
  '    c->version.header.type = FFX_API_DESC_TYPE_OVERRIDE_VERSION;\n'
  '    c->version.versionId = l.version_id;\n'
  '    c->backend.header.pNext = &c->version.header;\n'
  '#ifndef _WIN32\n'
  "    // (linux) fsr4-vk looks for the SDK's older backend description, not ffxCreateBackendVKDesc: without "
  'it, it finds no device\n'
  '    // and creation returns FFX_API_RETURN_ERROR_PARAMETER. Both stay chained\n'
  '    c->legacy_backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK_DEPRECATED;\n'
  '    c->legacy_backend.vkDevice = l.device_context.vkDevice;\n'
  '    c->legacy_backend.vkPhysicalDevice = l.device_context.vkPhysicalDevice;\n'
  '    c->legacy_backend.vkDeviceProcAddr = l.device_context.vkDeviceProcAddr;\n'
  '    c->version.header.pNext = &c->legacy_backend.header;\n'
  '#endif\n'
  '    c->upscale.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;\n'
  '    c->upscale.header.pNext = &c->backend.header;\n'
  "    // (the chain's colour is tonemapped and square-root encoded already: LDR, perceptual, no auto "
  'exposure; depth not\n'
  "    // inverted. The render size changes under the one context. With the game's native HDR the chain "
  'gives linear light\n'
  "    // past 1 (TemporalEngine::hdr): an HDR context, linear, with AMD's auto exposure)\n"
  '    c->upscale.flags = (hdr ? FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE\n'
  '                            : FFX_UPSCALE_ENABLE_NON_LINEAR_COLORSPACE) |\n'
  '                       FFX_UPSCALE_ENABLE_DYNAMIC_RESOLUTION;\n'
  '    c->upscale.maxRenderSize = {w, h};\n'
  '    c->upscale.maxUpscaleSize = {w, h};\n'
  '    c->upscale.fpMessage = &on_message;\n'
  '    const auto t0 = std::chrono::steady_clock::now();\n'
  '    const ffxReturnCode_t r = l.create(&c->context, &c->upscale.header, nullptr);\n'
  '    const double made_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - '
  't0).count();\n'
  '    if (r != FFX_API_RETURN_OK || !c->context) {\n'
  '        logf("vk: AMD FSR 4: its upscaler was not made (%d) for %ux%u", (int)r, w, h);\n'
  '        c->context = nullptr;\n'
  '        return nullptr;\n'
  '    }\n'
  '    c->width = w, c->height = h, c->hdr = hdr;\n'
  '    FfxApiEffectMemoryUsage usage{};\n'
  '    ffxQueryDescUpscaleGetGPUMemoryUsage mem{};\n'
  '    mem.header.type = FFX_API_QUERY_DESC_TYPE_UPSCALE_GPU_MEMORY_USAGE;\n'
  '    mem.gpuMemoryUsageUpscaler = &usage;\n'
  '    if (l.query(&c->context, &mem.header) == FFX_API_RETURN_OK) c->memory = usage.totalUsageInBytes;\n'
  '    ffxQueryGetProviderVersion provider{};\n'
  '    provider.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;\n'
  '    const bool known = l.query(&c->context, &provider.header) == FFX_API_RETURN_OK && '
  'provider.versionName;\n'
  '    logf("vk: AMD FSR 4: FSR %s made for outputs of %ux%u (frame %llu, %.1f ms of CPU; its own %llu '
  'MB)%s",\n'
  '         known ? provider.versionName : "?", w, h, (unsigned long long)texture_frame_no(), made_ms,\n'
  '         (unsigned long long)(c->memory >> 20), hdr ? ", HDR colour, linear (the game\'s native HDR)" : '
  '"");\n'
  '    return c;\n'
  '}\n',
  'template<bool Fsr316> std::shared_ptr<Context> make_context(uint32_t w, uint32_t h, bool hdr) {\n'
  '    Library& l = lib();\n'
  '    auto c = std::make_shared<Context>();\n'
  '    c->backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK;\n'
  '    c->backend.deviceContext = l.device_context;\n'
  "    // FSR 4's ML shader tuning must never rewrite the analytical 3.1.6 passes.\n"
  '    if (Fsr316) c->backend.deviceContext.vkDeviceProcAddr = vkGetDeviceProcAddr;\n'
  '    c->version.header.type = FFX_API_DESC_TYPE_OVERRIDE_VERSION;\n'
  '    c->version.versionId = Fsr316 ? l.version316_id : l.version_id;\n'
  '    c->backend.header.pNext = &c->version.header;\n'
  '    c->api_version.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE_VERSION;\n'
  '    c->api_version.version = FFX_UPSCALER_VERSION;\n'
  '    c->version.header.pNext = &c->api_version.header;\n'
  '#ifndef _WIN32\n'
  "    // (linux) fsr4-vk looks for the SDK's older backend description, not ffxCreateBackendVKDesc: without "
  'it, it finds no device\n'
  '    // and creation returns FFX_API_RETURN_ERROR_PARAMETER. Both stay chained\n'
  '    c->legacy_backend.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_BACKEND_VK_DEPRECATED;\n'
  '    c->legacy_backend.vkDevice = l.device_context.vkDevice;\n'
  '    c->legacy_backend.vkPhysicalDevice = l.device_context.vkPhysicalDevice;\n'
  '    c->legacy_backend.vkDeviceProcAddr = c->backend.deviceContext.vkDeviceProcAddr;\n'
  '    c->api_version.header.pNext = &c->legacy_backend.header;\n'
  '#endif\n'
  '    c->upscale.header.type = FFX_API_CREATE_CONTEXT_DESC_TYPE_UPSCALE;\n'
  '    c->upscale.header.pNext = &c->backend.header;\n'
  "    // (the chain's colour is tonemapped and square-root encoded already: LDR, perceptual, no auto "
  'exposure; depth not\n'
  "    // inverted. The render size changes under the one context. With the game's native HDR the chain "
  'gives linear light\n'
  "    // past 1 (TemporalEngine::hdr): an HDR context, linear, with AMD's auto exposure)\n"
  '    c->upscale.flags = (hdr ? FFX_UPSCALE_ENABLE_HIGH_DYNAMIC_RANGE | FFX_UPSCALE_ENABLE_AUTO_EXPOSURE\n'
  '                            : FFX_UPSCALE_ENABLE_NON_LINEAR_COLORSPACE) |\n'
  '                       FFX_UPSCALE_ENABLE_DYNAMIC_RESOLUTION;\n'
  '    c->upscale.maxRenderSize = {w, h};\n'
  '    c->upscale.maxUpscaleSize = {w, h};\n'
  '    c->upscale.fpMessage = &on_message<Fsr316>;\n'
  '    if (env_switch("OCR_FSR_API_DEBUG") == 1) c->upscale.flags |= FFX_UPSCALE_ENABLE_DEBUG_CHECKING;\n'
  '    const auto t0 = std::chrono::steady_clock::now();\n'
  '    const ffxReturnCode_t r = l.create(&c->context, &c->upscale.header, nullptr);\n'
  '    const double made_ms = std::chrono::duration<double, std::milli>(std::chrono::steady_clock::now() - '
  't0).count();\n'
  '    if (r != FFX_API_RETURN_OK || !c->context) {\n'
  '        logf("vk: AMD FSR %s: its upscaler was not made (%d) for %ux%u", Fsr316 ? "3.1.6" : "4", (int)r, '
  'w, h);\n'
  '        c->context = nullptr;\n'
  '        return nullptr;\n'
  '    }\n'
  '    c->width = w, c->height = h, c->hdr = hdr;\n'
  '    FfxApiEffectMemoryUsage usage{};\n'
  '    ffxQueryDescUpscaleGetGPUMemoryUsage mem{};\n'
  '    mem.header.type = FFX_API_QUERY_DESC_TYPE_UPSCALE_GPU_MEMORY_USAGE;\n'
  '    mem.gpuMemoryUsageUpscaler = &usage;\n'
  '    if (l.query(&c->context, &mem.header) == FFX_API_RETURN_OK) c->memory = usage.totalUsageInBytes;\n'
  '    ffxQueryGetProviderVersion provider{};\n'
  '    provider.header.type = FFX_API_QUERY_DESC_TYPE_GET_PROVIDER_VERSION;\n'
  '    const bool known = l.query(&c->context, &provider.header) == FFX_API_RETURN_OK && '
  'provider.versionName;\n'
  '    if (Fsr316 && (!known || strcmp(provider.versionName, "3.1.6"))) {\n'
  '        logf("vk: AMD FSR 3.1.6: wrong provider returned (%s); context rejected", known ? '
  'provider.versionName : "unknown");\n'
  '        return nullptr;\n'
  '    }\n'
  '    logf("vk: AMD FSR %s: FSR %s made for outputs of %ux%u (frame %llu, %.1f ms of CPU; its own %llu '
  'MB)%s",\n'
  '         Fsr316 ? "3.1.6" : "4", known ? provider.versionName : "?", w, h, (unsigned long '
  'long)texture_frame_no(), made_ms,\n'
  '         (unsigned long long)(c->memory >> 20), hdr ? ", linear colour, automatic exposure" : "");\n'
  '    return c;\n'
  '}\n'),
 ('gpu/vk/vk_fsr4.cpp',
  'bool start() { return load(); }\n'
  '\n'
  'void release() {\n'
  '    State& s = st();\n'
  '    if (!s.context) return;\n'
  '    std::shared_ptr<Context> old = std::move(s.context);\n'
  '    temporal_later([old] {});   // (destroyed with the last copy, a few frames on: recorded dispatches '
  'may still use it)\n'
  '    s.context.reset();\n'
  '}\n'
  '\n'
  'int prepare(VkCommandBuffer, uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh, bool /*native_aa*/,\n'
  '            uint32_t* in_w, uint32_t* in_h, const char** why) {\n'
  '    State& s = st();\n'
  '    int made = 1;\n'
  "    // (the game's native HDR: Context::hdr. What the game presents, not the option and the swapchain: "
  'with Native picked and\n'
  "    // the game's picture not PQ, the scene is LDR. RX_VK_FSR4_HDR=0: the LDR context and the clamped "
  'colour with Native too)\n'
  '    static const bool hdr_allowed = env_switch("RX_VK_FSR4_HDR") != 0;\n'
  '    const bool hdr = hdr_allowed && present_native_pq.load(std::memory_order_relaxed);\n'
  '    if (!s.context || s.context->width != ow || s.context->height != oh || s.context->hdr != hdr) {\n'
  '        if (s.context && s.context->hdr != hdr) logf("vk: AMD FSR 4: made again: the game\'s native HDR '
  'turned %s", hdr ? "on" : "off");\n'
  '        release();\n'
  '        s.context = make_context(ow, oh, hdr);\n'
  '        if (!s.context) return *why = "its upscaler was not made", -1;\n'
  '        s.in_w = s.in_h = 0;\n'
  '        made = 2;\n'
  '    }\n'
  '    // (the inputs as large as the largest render size this context has had, never past the output: a '
  'fixed share keeps\n'
  "    // images of its own size, and the game's dynamic resolution only makes them again when it goes past "
  'them)\n'
  '    s.in_w = std::min(std::max(s.in_w, rw), ow), s.in_h = std::min(std::max(s.in_h, rh), oh);\n'
  '    *in_w = s.in_w, *in_h = s.in_h;\n'
  '    return made;\n'
  '}\n'
  '\n'
  'bool evaluate(VkCommandBuffer cmd, const TemporalFrame& f) {\n'
  '    State& s = st();\n'
  '    Library& l = lib();\n'
  '#ifndef _WIN32\n'
  '    TemporalImage exposure{};\n'
  '    if (!unit_exposure(cmd, exposure)) return false;\n'
  '#endif\n'
  '    const auto now = std::chrono::steady_clock::now();\n'
  '    const float frame_ms = s.evals ? std::chrono::duration<float, std::milli>(now - s.last).count() : '
  '1000.0f / 30.0f;\n'
  '    s.last = now;\n'
  '\n'
  '    constexpr VkImageLayout G = VK_IMAGE_LAYOUT_GENERAL, R = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;\n'
  '    constexpr VkAccessFlags2 any = VK_ACCESS_2_MEMORY_READ_BIT | VK_ACCESS_2_MEMORY_WRITE_BIT;\n'
  '    const VkImageMemoryBarrier2 in[4] = {barrier(f.color.image, VK_ACCESS_2_MEMORY_WRITE_BIT, '
  'VK_ACCESS_2_SHADER_READ_BIT, G, R),\n'
  '                                         barrier(f.depth.image, VK_ACCESS_2_MEMORY_WRITE_BIT, '
  'VK_ACCESS_2_SHADER_READ_BIT, G, R),\n'
  '                                         barrier(f.motion.image, VK_ACCESS_2_MEMORY_WRITE_BIT, '
  'VK_ACCESS_2_SHADER_READ_BIT, G, R),\n'
  '                                         barrier(f.output.image, any, any, G, G)};\n'
  '    barriers(cmd, in, 4);\n'
  '\n'
  '    ffxDispatchDescUpscale d{};\n'
  '    d.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE;\n'
  '    d.commandList = cmd;\n'
  '    d.color = resource(f.color, VK_IMAGE_USAGE_SAMPLED_BIT, FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.depth = resource(f.depth, VK_IMAGE_USAGE_SAMPLED_BIT, FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.motionVectors = resource(f.motion, VK_IMAGE_USAGE_SAMPLED_BIT, '
  'FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.output = resource(f.output, VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, '
  'FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);\n'
  '#ifndef _WIN32\n'
  '    if (!s.context->hdr)   // (an HDR context works out its own exposure: '
  'FFX_UPSCALE_ENABLE_AUTO_EXPOSURE)\n'
  '        d.exposure = resource(exposure, VK_IMAGE_USAGE_SAMPLED_BIT, '
  'FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '#endif\n'
  '    d.jitterOffset = {f.jitter[0], f.jitter[1]};   // (render pixels, as the projection was offset: the '
  "same as DLSS's)\n"
  '    d.motionVectorScale = {1.0f, 1.0f};             // (render pixels already, towards the frame before)\n'
  '    d.renderSize = {f.render_w, f.render_h};\n'
  '    d.upscaleSize = {f.output.width, f.output.height};\n'
  '    d.enableSharpening = false;   // (the Sharpness row sharpens at the window, after the HUD)\n'
  '    d.sharpness = 0.0f;\n'
  '    d.frameTimeDelta = frame_ms;\n'
  '    d.preExposure = 1.0f;\n'
  '    d.reset = f.reset;\n'
  '    d.cameraNear = f.near_z, d.cameraFar = f.far_z, d.cameraFovAngleVertical = f.fov_y;\n'
  '    d.viewSpaceToMetersFactor = 1.0f;\n'
  '    d.flags = s.context->hdr ? 0u : (uint32_t)FFX_UPSCALE_FLAG_NON_LINEAR_COLOR_SRGB;   // (HDR: linear '
  'light)\n'
  '    ffxReturnCode_t r;\n'
  '    {\n'
  '        GprofSpan timed(cmd, "fsr4 ffxDispatch (AMD\'s passes)");   // (RX_VK_PASS_TIMING=1: AMD\'s own '
  'GPU time, named)\n'
  '        ::mkwvk::rec::boundary(::mkwvk::rec::B_DIRECT);   // (ffxDispatch records into cmd itself: what '
  'this thread recorded through vk_work.h reaches cmd first)\n'
  '        r = l.dispatch(&s.context->context, &d.header);\n'
  "        note_work();   // (AMD's dispatches: full_barrier must not take the next barrier for a repeat of "
  'the one before them)\n'
  '    }\n'
  '\n'
  '    const VkImageMemoryBarrier2 out[4] = {barrier(f.color.image, VK_ACCESS_2_SHADER_READ_BIT, any, R, '
  'G),\n'
  '                                          barrier(f.depth.image, VK_ACCESS_2_SHADER_READ_BIT, any, R, '
  'G),\n'
  '                                          barrier(f.motion.image, VK_ACCESS_2_SHADER_READ_BIT, any, R, '
  'G),\n'
  '                                          barrier(f.output.image, any, any, G, G)};\n'
  '    barriers(cmd, out, 4);\n'
  '    if (r != FFX_API_RETURN_OK) {\n'
  '        logf("vk: AMD FSR 4: its dispatch failed (%d)", (int)r);\n'
  '        return false;\n'
  '    }\n'
  '    // (the first evaluation, and the first resets: a camera cut each)\n'
  '    if (s.evals++ == 0 || (f.reset && s.told_resets < 40))\n'
  '        s.told_resets++, logf("vk: AMD FSR 4: %ux%u -> %ux%u, jitter %+.3f %+.3f px%s", f.render_w, '
  'f.render_h, f.output.width,\n'
  '                              f.output.height, f.jitter[0], f.jitter[1], f.reset ? " (history reset)" : '
  '"");\n'
  '    return true;\n'
  '}\n'
  '\n'
  'uint64_t memory() {\n'
  '    State& s = st();\n'
  '    return s.context ? s.context->memory : 0;\n'
  '}\n'
  '\n'
  "/// Its context takes HDR colour (made for the game's native HDR): the chain gives it linear light, "
  'unclamped\n'
  'bool hdr() {\n'
  '    State& s = st();\n'
  '    return s.context && s.context->hdr;\n'
  '}\n'
  '\n'
  'const TemporalEngine kEngine{"AMD FSR 4", "FSR", start, prepare, evaluate, release, memory, hdr};\n',
  'template<bool Fsr316> bool start() {\n'
  '    return load() && (Fsr316 ? fsr316_why() : fsr4_why()) == FSR_OK;\n'
  '}\n'
  '\n'
  'template<bool Fsr316> void release() {\n'
  '    State& s = st<Fsr316>();\n'
  '    if (!s.context) return;\n'
  '    std::shared_ptr<Context> old = std::move(s.context);\n'
  '    temporal_later([old] {});   // (destroyed with the last copy, a few frames on: recorded dispatches '
  'may still use it)\n'
  '    s.context.reset();\n'
  '}\n'
  '\n'
  'template<bool Fsr316> int prepare(VkCommandBuffer, uint32_t rw, uint32_t rh, uint32_t ow, uint32_t oh, '
  'bool /*native_aa*/,\n'
  '            uint32_t* in_w, uint32_t* in_h, const char** why) {\n'
  '    State& s = st<Fsr316>();\n'
  '    int made = 1;\n'
  "    // (the game's native HDR: Context::hdr. What the game presents, not the option and the swapchain: "
  'with Native picked and\n'
  "    // the game's picture not PQ, the scene is LDR. RX_VK_FSR4_HDR=0: the LDR context and the clamped "
  'colour with Native too)\n'
  '    static const bool hdr_allowed = env_switch("RX_VK_FSR4_HDR") != 0;\n'
  "    // FSR 3.1.6 requires linear colour, also for SDR output. The chain's\n"
  '    // existing linear input/output passes provide it without changing display HDR.\n'
  '    const bool hdr = Fsr316 || (hdr_allowed && present_native_pq.load(std::memory_order_relaxed));\n'
  '    if (!s.context || s.context->width != ow || s.context->height != oh || s.context->hdr != hdr) {\n'
  '        if (s.context && s.context->hdr != hdr) logf("vk: AMD FSR 4: made again: the game\'s native HDR '
  'turned %s", hdr ? "on" : "off");\n'
  '        release<Fsr316>();\n'
  '        s.context = make_context<Fsr316>(ow, oh, hdr);\n'
  '        if (!s.context) return *why = "its upscaler was not made", -1;\n'
  '        s.in_w = s.in_h = 0;\n'
  '        made = 2;\n'
  '    }\n'
  '    // (the inputs as large as the largest render size this context has had, never past the output: a '
  'fixed share keeps\n'
  "    // images of its own size, and the game's dynamic resolution only makes them again when it goes past "
  'them)\n'
  '    s.in_w = std::min(std::max(s.in_w, rw), ow), s.in_h = std::min(std::max(s.in_h, rh), oh);\n'
  '    *in_w = s.in_w, *in_h = s.in_h;\n'
  '    return made;\n'
  '}\n'
  '\n'
  'template<bool Fsr316> bool evaluate(VkCommandBuffer cmd, const TemporalFrame& f) {\n'
  '    State& s = st<Fsr316>();\n'
  '    Library& l = lib();\n'
  '    TemporalImage exposure{};\n'
  '    if (!s.context->hdr && !unit_exposure(cmd, exposure)) return false;\n'
  '    const auto now = std::chrono::steady_clock::now();\n'
  '    const float frame_ms = s.evals ? std::chrono::duration<float, std::milli>(now - s.last).count() : '
  '1000.0f / 30.0f;\n'
  '    s.last = now;\n'
  '\n'
  '    constexpr VkImageLayout G = VK_IMAGE_LAYOUT_GENERAL, R = VK_IMAGE_LAYOUT_SHADER_READ_ONLY_OPTIMAL;\n'
  '    constexpr VkAccessFlags2 any = VK_ACCESS_2_MEMORY_READ_BIT | VK_ACCESS_2_MEMORY_WRITE_BIT;\n'
  '    const VkImageMemoryBarrier2 in[4] = {barrier(f.color.image, VK_ACCESS_2_MEMORY_WRITE_BIT, '
  'VK_ACCESS_2_SHADER_READ_BIT, G, R),\n'
  '                                         barrier(f.depth.image, VK_ACCESS_2_MEMORY_WRITE_BIT, '
  'VK_ACCESS_2_SHADER_READ_BIT, G, R),\n'
  '                                         barrier(f.motion.image, VK_ACCESS_2_MEMORY_WRITE_BIT, '
  'VK_ACCESS_2_SHADER_READ_BIT, G, R),\n'
  '                                         barrier(f.output.image, any, any, G, G)};\n'
  '    barriers(cmd, in, 4);\n'
  '\n'
  '    ffxDispatchDescUpscale d{};\n'
  '    d.header.type = FFX_API_DISPATCH_DESC_TYPE_UPSCALE;\n'
  '    d.commandList = cmd;\n'
  '    d.color = resource(f.color, VK_IMAGE_USAGE_SAMPLED_BIT, FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.depth = resource(f.depth, VK_IMAGE_USAGE_SAMPLED_BIT, FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.motionVectors = resource(f.motion, VK_IMAGE_USAGE_SAMPLED_BIT, '
  'FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.output = resource(f.output, VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT, '
  'FFX_API_RESOURCE_STATE_UNORDERED_ACCESS);\n'
  '    if (!s.context->hdr)   // (an HDR context works out its own exposure: '
  'FFX_UPSCALE_ENABLE_AUTO_EXPOSURE)\n'
  '        d.exposure = resource(exposure, VK_IMAGE_USAGE_SAMPLED_BIT, '
  'FFX_API_RESOURCE_STATE_COMPUTE_READ);\n'
  '    d.jitterOffset = {f.jitter[0], f.jitter[1]};   // (render pixels, as the projection was offset: the '
  "same as DLSS's)\n"
  '    d.motionVectorScale = {1.0f, 1.0f};             // (render pixels already, towards the frame before)\n'
  '    d.renderSize = {f.render_w, f.render_h};\n'
  '    d.upscaleSize = {f.output.width, f.output.height};\n'
  '    d.enableSharpening = false;   // (the Sharpness row sharpens at the window, after the HUD)\n'
  '    d.sharpness = 0.0f;\n'
  '    d.frameTimeDelta = frame_ms;\n'
  '    d.preExposure = 1.0f;\n'
  '    d.reset = f.reset;\n'
  '    d.cameraNear = f.near_z, d.cameraFar = f.far_z, d.cameraFovAngleVertical = f.fov_y;\n'
  '    d.viewSpaceToMetersFactor = 1.0f;\n'
  '    d.flags = s.context->hdr ? 0u : (uint32_t)FFX_UPSCALE_FLAG_NON_LINEAR_COLOR_SRGB;   // (HDR: linear '
  'light)\n'
  '    ffxReturnCode_t r;\n'
  '    {\n'
  '        GprofSpan timed(cmd, Fsr316 ? "fsr316 ffxDispatch (AMD\'s passes)" : "fsr4 ffxDispatch (AMD\'s '
  'passes)");   // (RX_VK_PASS_TIMING=1: AMD\'s own GPU time, named)\n'
  '        ::mkwvk::rec::boundary(::mkwvk::rec::B_DIRECT);   // (ffxDispatch records into cmd itself: what '
  'this thread recorded through vk_work.h reaches cmd first)\n'
  '        r = l.dispatch(&s.context->context, &d.header);\n'
  "        note_work();   // (AMD's dispatches: full_barrier must not take the next barrier for a repeat of "
  'the one before them)\n'
  '    }\n'
  '\n'
  '    const VkImageMemoryBarrier2 out[4] = {barrier(f.color.image, VK_ACCESS_2_SHADER_READ_BIT, any, R, '
  'G),\n'
  '                                          barrier(f.depth.image, VK_ACCESS_2_SHADER_READ_BIT, any, R, '
  'G),\n'
  '                                          barrier(f.motion.image, VK_ACCESS_2_SHADER_READ_BIT, any, R, '
  'G),\n'
  '                                          barrier(f.output.image, any, any, G, G)};\n'
  '    barriers(cmd, out, 4);\n'
  '    if (r != FFX_API_RETURN_OK) {\n'
  '        logf("vk: AMD FSR %s: its dispatch failed (%d)", Fsr316 ? "3.1.6" : "4", (int)r);\n'
  '        return false;\n'
  '    }\n'
  '    // (the first evaluation, and the first resets: a camera cut each)\n'
  '    if (s.evals++ == 0 || (f.reset && s.told_resets < 40))\n'
  '        s.told_resets++, logf("vk: AMD FSR %s: %ux%u -> %ux%u, jitter %+.3f %+.3f px%s", Fsr316 ? "3.1.6" '
  ': "4", f.render_w, f.render_h, f.output.width,\n'
  '                              f.output.height, f.jitter[0], f.jitter[1], f.reset ? " (history reset)" : '
  '"");\n'
  '    return true;\n'
  '}\n'
  '\n'
  'template<bool Fsr316> uint64_t memory() {\n'
  '    State& s = st<Fsr316>();\n'
  '    return s.context ? s.context->memory : 0;\n'
  '}\n'
  '\n'
  "/// Its context takes HDR colour (made for the game's native HDR): the chain gives it linear light, "
  'unclamped\n'
  'template<bool Fsr316> bool hdr() {\n'
  '    State& s = st<Fsr316>();\n'
  '    return s.context && s.context->hdr;\n'
  '}\n'
  '\n'
  'const TemporalEngine kEngine{"AMD FSR 4", "FSR", start<false>, prepare<false>, evaluate<false>, '
  'release<false>, memory<false>, hdr<false>};\n'
  'const TemporalEngine kEngine316{"AMD FSR 3.1.6", "FSR316", start<true>, prepare<true>, evaluate<true>, '
  'release<true>, memory<true>, hdr<true>};\n'),
 ('gpu/vk/vk_fsr4.cpp',
  'const TemporalEngine* fsr4_engine() { return &kEngine; }',
  'const TemporalEngine* fsr4_engine() { return &kEngine; }\n'
  'const TemporalEngine* fsr316_engine() { return &kEngine316; }'),
 ('gpu/vk/vk_fsr4.cpp',
  '\nvoid fsr4_close() { tune::close(); }',
  '\n'
  'void fsr316_probe() {\n'
  '    if (fsr316_why() != FSR_OK || g_316_why.load(std::memory_order_relaxed) >= 0 || !dev.device) return;\n'
  '    load();\n'
  '}\n'
  '\n'
  'void fsr4_close() { tune::close(); }'),
 ('gpu/vk/vk_fsr4.cpp',
  'const TemporalEngine* fsr4_engine() { return nullptr; }',
  'const TemporalEngine* fsr4_engine() { return nullptr; }\n'
  'const TemporalEngine* fsr316_engine() { return nullptr; }\n'
  'void fsr316_probe() {}'),
 ('gpu/vk/vk_fsr4.h',
  'FsrWhy fsr4_why();',
  'FsrWhy fsr4_why();\n'
  '/// Analytical FSR 3.1.6 from the same AMD runtime; independent of FSR 4 support.\n'
  'FsrWhy fsr316_why();\n'
  'void fsr316_probe();\n'
  'const TemporalEngine* fsr316_engine();'),
 ('gpu/vk/upscaler_rows.h', 'OFF = 6, kUpscalers = 7', 'OFF = 6, FSR316 = 7, kUpscalers = 8'),
 ('gpu/vk/upscaler_rows.h',
  'inline bool is_dlss(int upscaler)',
  '/// Keep separate histories/failed states for the runtime 3.1.6 provider.\n'
  'inline int temporal_slot(int mode) { return mode == FSR316 ? 3 : (mode == FSR4 || mode == FSR4_AA) ? 1 : '
  'mode == FSR3 ? 2 : 0; }\n'
  'inline bool is_dlss(int upscaler)'),
 ('gpu/vk/upscaler_rows.h',
  'upscaler == DLSS || upscaler == FSR3 || upscaler == FSR4;',
  'upscaler == DLSS || upscaler == FSR3 || upscaler == FSR316 || upscaler == FSR4;'),
 ('gpu/vk/upscaler_rows.h', 'if (upscaler == FSR3)', 'if (upscaler == FSR3 || upscaler == FSR316)'),
 ('gpu/vk/upscaler_rows.h',
  'kEngines[] = {GAME, DLSS, FSR3, FSR4, OFF}',
  'kEngines[] = {GAME, DLSS, FSR3, FSR316, FSR4, OFF}'),
 ('gpu/vk/vk_temporal.cpp',
  'if (!ur::is_dlss(v) && !ur::is_fsr4(v)) return ur::GAME;',
  'if (!ur::is_dlss(v) && !ur::is_fsr4(v) && v != ur::FSR316) return ur::GAME;'),
 ('gpu/vk/vk_temporal.cpp',
  '    if (fsr3_wanted()) return ur::GAME;',
  '    if (fsr3_wanted()) return ur::GAME;\n'
  '    if (v == ur::FSR316 && fsr316_why() != FSR_OK) return ur::GAME;'),
 ('gpu/vk/vk_temporal.cpp', 'Engine engines[3];', 'Engine engines[4];'),
 ('gpu/vk/vk_temporal.cpp',
  'const int slot = ur::is_fsr4(mode) ? 1 : mode == ur::FSR3 ? 2 : 0;',
  'const int slot = ur::temporal_slot(mode);'),
 ('gpu/vk/vk_temporal.cpp',
  'if (!k.e) k.e = slot == 1 ? fsr4_engine() : slot == 2 ? fsr3_engine() : dlss_engine();',
  'if (!k.e) k.e = slot == 3 ? fsr316_engine() : slot == 1 ? fsr4_engine() : slot == 2 ? fsr3_engine() : '
  'dlss_engine();'),
 ('gpu/vk/vk_temporal.cpp',
  '    case ur::FSR3: return "AMD FSR 3.1";',
  '    case ur::FSR3: return "AMD FSR 3.1";\n    case ur::FSR316: return "AMD FSR 3.1.6";'),
 ('gpu/vk/vk_temporal.cpp',
  's.engines[ur::is_fsr4(mode) ? 1 : mode == ur::FSR3 ? 2 : 0].failed',
  's.engines[ur::temporal_slot(mode)].failed'),
 ('gpu/vk/vk_menu.cpp',
  '(fsr3::supported() ? ur::bit(ur::FSR3) : 0u) | ur::fsr4_bits(fsr4_why() == FSR_OK);',
  '(fsr3::supported() ? ur::bit(ur::FSR3) : 0u) | ur::fsr4_bits(fsr4_why() == FSR_OK) |\n'
  '           (fsr316_why() == FSR_OK ? ur::bit(ur::FSR316) : 0u);'),
 ('gpu/vk/vk_menu.cpp',
  '"AMD FSR 4 Native AA", "Off (no upscaling)"};',
  '"AMD FSR 4 Native AA", "Off (no upscaling)", "AMD FSR 3.1.6"};'),
 ('gpu/vk/vk_menu.cpp',
  '"fastest choice and the roughest picture: no edge smoothing, and softer below 100%.",',
  '"fastest choice and the roughest picture: no edge smoothing, and softer below 100%.",\n'
  '        "AMD FSR 3.1.6 upscaling. Select 67% for Quality, 58% for Balanced, or 100% for native '
  'anti-aliasing.",'),
 ('gpu/vk/vk_menu.cpp',
  '    int d = 0, f = 0;',
  '    if (variant < 0 && opts.dlss == ur::FSR316 && fsr316_why() != FSR_OK)\n'
  '        return "AMD FSR 3.1.6 is unavailable in this run. The game\'s own upscaler is active; the saved '
  'choice is kept.";\n'
  '    int d = 0, f = 0;'),
 ('gpu/vk/vk_menu.cpp',
  '            fsr4_probe();',
  '            fsr4_probe();\n            fsr316_probe();'),
 ('gpu/vk/vk_menu.cpp',
  'if (open_now.load()) dlss_probe(), fsr4_probe();',
  'if (open_now.load()) dlss_probe(), fsr4_probe(), fsr316_probe();'),
 ('gpu/vk/vk_fsr4.cpp',
  '    ffxOverrideVersion version{};',
  '    ffxOverrideVersion version{};\n    ffxCreateContextDescUpscaleVersion api_version{};'),
 ('gpu/vk/vk_fsr4.cpp',
  '#ifndef _WIN32\n'
  "/// (linux) a Vulkan FSR 4 build takes no frame without an exposure, and the chain's colour is tonemapped "
  'already: a 1x1 R32F of 1',
  '/// SDR FSR 4 requires an explicit exposure when automatic exposure is disabled.\n'
  '/// The input is already tonemapped: supply a 1x1 R32F of 1 on every platform.'),
 ('gpu/vk/vk_fsr4.cpp',
  '    return true;\n}\n#endif\n\n// ---- the engine',
  '    return true;\n}\n\n// ---- the engine')]

def apply(root):
    root = Path(root)
    for rel, old, new in CHANGES:
        p = root / rel
        text = p.read_text(encoding='utf-8')
        p.write_text(replace_once(text, old, new), encoding='utf-8', newline='\n')
