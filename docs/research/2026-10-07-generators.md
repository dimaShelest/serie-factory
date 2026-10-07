# Дослідження генераторів (Seedance 2.x, Nano Banana, ElevenLabs, lip-sync) — 2026-10-07

> Зібрано агентами з відкритих джерел і перевірено фактчекером (частини 1–3 — виправлення й доповнення, частина 4 — повний посібник). Мова — англійська (цитати й параметри API). Позначка UNVERIFIED — не підтверджено. Схеми моделей змінюються: перед підключенням автоматики звір із живою схемою провайдера.

# Fact-check of the serie-factory build guide (2026-10-07)

**Access limits during this check**
- The shared WebSearch budget was used up before this check started, so I ran no new web searches.
- The proxy blocked replicate.com, x.com, seed.bytedance.com, fal.ai and volcengine.
- I re-checked claims by fetching the raw files the guide cites, plus other GitHub-hosted captures, using WebFetch, curl and GitHub code search.
- One new primary source was reachable: **Cloudflare's official model catalog** (cloudflare-docs). Cloudflare owns Replicate and serves the same Seedance models.

---

## Part 1. Corrections (claim → verified truth + source)

| # | Guide claim | Verified truth | Source (date) |
|---|---|---|---|
| C1 | §1.4 / §6.2 / §8 P0: frontal photoreal faces are "likely rejected" on Replicate; Cloudflare `use_virtual_avatar` pass rate UNVERIFIED | **Field test on Seedance 2.5 dated 2026-10-07.** Without the flag, every portrait and every character sheet with a face was refused on both Replicate and Cloudflare. A sheet with no face passed, but the model invented a new face. With `use_virtual_avatar:true` on Cloudflare, an AI-made photoreal portrait passed both as a reference and as a start frame, and the face matched in every frame. **Caveats:** (1) with the flag on, `image` "guides the face only and does not fix the opening shot"; (2) 2.0 and 2.0 Fast cap at 12 s with the flag; (3) the flag is a promise that the person is AI-made and that you hold the rights. ComfyUI shipped "Seedance blocks realistic human faces, even AI-generated ones" (merged 2026-09-30). **A clear face on the Replicate route is a no-go, not an open question.** | [VSB-S] https://github.com/visualsandbox/skills/blob/main/skills/vsb-seedance/SKILL.md (tests 2026-10-07); [VSB-V] https://github.com/visualsandbox/skills/blob/main/skills/vsb-video/SKILL.md; [COMFYPR] https://github.com/Comfy-Org/ComfyUI_frontend/pull/19638 (2026-09-30) |
| C2 | §1.1: 2.5 at 1080p is a conflict; ComfyUI shows 1080p | **Replicate and Cloudflare: 480p/720p only.** This is confirmed by Cloudflare's official catalog metadata ("Resolutions: 480p, 720p", 2026-08-07) and the Replicate schema captured 2026-10-05. **ModelArk (BytePlus) now offers 2.5 at 1080p:** ComfyUI's `nodes_bytedance.py` (fetched 2026-10-07) lists `["480p","720p","1080p"]` for 2.5, plus a Draft (480p) → 1080p-final path. ark-mcp PR #83 (merged 2026-10-03) says the same. The 2026-08-09 spec digest ("no path above 720p on 2.5") is outdated for ModelArk. Whether that 1080p is native or upscaled is UNVERIFIED. | [CFDOC25] https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/catalog-models/bytedance-seedance-2.5.json; [GFV]; [COMFY]; [ARK83] |
| C3 | §2.6: default dialogue syntax `{}` on 2.5 "following the official guide" | The official 2.5 guide's own worked example writes `Dialogue (<speaker>): "<line>"`. `{}` appears in the sd25-pe formula and in another rendering of the guide, so both forms are ByteDance material. The Replicate schema says "use double quotes in prompt". ComfyUI's 2.5 node tooltip says "Put spoken lines in double quotes". **Default to double quotes on both versions; keep `{}` as an A/B arm.** | [SD25G mirror §7] https://raw.githubusercontent.com/JPG-GITY/byteplus-docs-sync/main/skill/references/video-seedance-2.5-prompt-guide.md (captured 2026-08-09); [RS25]; [COMFY] |
| C4 | §4.3: "Seedance 2.5: never put several views in one collage image [SD25G]" | The official 2.5 guide says: "for 1–5 subjects single- and multi-view both work. For >5 subjects, single-view is more stable — split views into separate images, never a collage." Multi-view subject images are "discouraged on 2.0, supported on 2.5". One view per image stays our convention (Gemini cookbook "no panels"), but on 2.5 it is not an official ban. | [SD25G mirror §3, §6] |
| C5 | §1.4 rule 6: when first- and last-frame ratios differ, "the first frame wins and the last is centre-cropped" | The 2.5 guide says a last frame with a different ratio "gets stretched". The rule is unchanged (supply both frames at the same ratio); the mechanism is a conflict. | [SD25G mirror §2]; [SD25SPEC] https://raw.githubusercontent.com/lukasersil/seedance-25/main/references/official-spec.md (last_verified 2026-08-09) |
| C6 | §2.1 rule 11 / §6.11 / §7.2: "drone" and "FPV" triggered E005; ban them | The official 2.5 guide lists "aerial, FPV, bullet time…" as named techniques that work. Cloudflare's own official 2.5 example prompt, "A dramatic drone shot flying through misty mountain peaks…", completed. **Downgrade to a soft lint:** prefer "aerial flythrough", but do not treat the word as an E005 cause. | [SD25G mirror §5]; [CFDOC25] examples |
| C7 | §1.7: Nano Banana 2 "deprecated 2026-10-06, shutdown 2026-10-29" | The **Gemini API** shuts down `gemini-3.1-flash-image` on 2026-10-29. **Vertex AI** lists a deprecation date of **2027-05-28**. Nano Banana: Gemini API 2026-10-02, Vertex 2027-03-15 (confirmed). What Replicate's `google/nano-banana(-2)` does depends on its backend, which is UNVERIFIED. Both Replicate pages were still priced on 2026-10-06. The advice (migrate) is unchanged. | [LITELLM] https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json (fetched 2026-10-07); [GFR] |
| C8 | §1.7: `nano-banana-2.1` shape "from … the [PUTER] catalog" | The Puter catalog (fetched 2026-10-07) has **no** `nano-banana-2.1` entry. The shape is extrapolated from NB2's Replicate schema. The model does exist on Replicate: priced 2026-10-06 at $0.0336 / $0.0504 / $0.1134, and modelpedia shows it "active" on 2026-10-07. **The field list is fully UNVERIFIED; validate it at startup.** | [PUTER]; [GFR]; [MPEDIA] |
| C9 | §1.8 / §5.2: `previous_text` / `next_text` "v4 support UNVERIFIED" | ElevenLabs' request-stitching guide shows `previous_request_ids` with `model_id="eleven_v4"` and says "Request stitching is not available for the `eleven_v3` model." The API reference adds: "In case both previous_text and previous_request_ids is send, previous_text will be ignored." **The v3 fallback loses stitching.** | [EL-STITCH] mirror of https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/request-stitching; [EL-API] |
| C10 | §2.8 E4 conflict: what `reference_audios` does | Official sd25-pe: "When written dialogue conflicts with the content of reference audio, the user's text controls the words. By default, the audio supplies only voice characteristics, accent, speed, and emotion." **Reference audio conditions the voice; it is not played back.** This resolves the conflict in favour of [A1]. | [SD25PE] line 227 |
| C11 | §1.8: `sync_mode` meanings UNVERIFIED; §5.9 default `silence` | Schema text: `sync_mode` is the "Lipsync mode when audio and video durations are out of sync", so it only handles a length mismatch. `active_speaker`: "whoever is speaking in the clip will be used for lipsync". Field practice: pad the WAV to the clip length and use `cut_off`. **Lipsync does not animate a still or closed mouth:** "a clip with no speaking motion gets no lip movement". So arm B must prompt visible speech motion. | [L1] genfeed schemas.json (fetchedAt 2026-03-06); [VSB-V] |
| C12 | §1.8: `lipsync-2-pro` "deprecated" per [L9], "likely noise" | modelpedia marks `lipsync-2` (2026-08-13), `lipsync-2-pro` (2026-09-27), `seedance-2.0-mini` and `nano-banana-2-lite` (both 2026-07-31) as "deprecated". The last two are live and priced in Aug–Oct 2026 per other sources. The flag is unreliable, and [VSB-V] still lists `lipsync-2-pro` in October 2026. Check the page. | [MPEDIA]; [POLL]; [GFR]; [VSB-V] |
| C13 | §1.5: 2.0 price conflict ($0.08 vs $0.07 at 480p) | This is a **provider difference, not an error.** Replicate (captured 2026-10-05): $0.08 / $0.18 / $0.45 / $1.00. Cloudflare official catalog: $0.07 / $0.15 / $0.37 / $0.78 (with video input $0.172 / $0.372 / $0.914 / $1.866). The 2.5 price is identical on both: $0.1028 / $0.2312, and $0.4304 / $0.9676 with video input. | [GFV]; [CFDOC20] https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/catalog-models/bytedance-seedance-2.0.json (created 2026-05-22); [CFDOC25] |
| C14 | §1.4 rule 7: unknown keys error or are dropped (conflict) | **Cloudflare's 2.0 and 2.5 schemas set `additionalProperties:false`, so unknown keys are rejected there.** Replicate behaviour remains UNVERIFIED. The rule (never send them) is unchanged. | [CFDOC25] |
| C15 | §1.6: [RIFF] I2V with `aspect_ratio:"16:9"` was accepted and the output followed the image | Caveat [RIFF] states itself: the source frame was already 16:9, "so this proves acceptance, not how an off-ratio frame is handled." Keep sending `adaptive`. | [RIFF] https://github.com/davidrd123/riff-mcp/blob/main/LIVE_VERIFICATION.md (2026-08-29) |
| C16 | §1.1: 2.5 supports 11 named languages | The official guide mirror I could read says only "Native generation in **10+ languages**", with no list. The 11-language list is UNVERIFIED. | [SD25G mirror §1] |
| C17 | §1.7: Pro reference caps "≤5 humans + ≤6 high-fidelity objects" | The Gemini cookbook (2026-10) says "up to 14 with Nano-Banana 2 and Pro, 6 with high fidelity", with no human count. "≤5 humans" is UNVERIFIED. | [COOKBOOK] Get_Started_Nano_Banana.ipynb |
| C18 | §1.8: v4 API list price $0.08 per 1K characters | Not verifiable from the docs I could reach. LiteLLM lists `eleven_v3` and `eleven_multilingual_v2` at $0.18 per 1K characters (`0.00018`/char), which conflicts. Mark UNVERIFIED and use the `character-cost` header. | [LITELLM] |
| C19 | §1.5: Mini prices $0.04 / $0.09 UNVERIFIED | A second source agrees: the pollinations registry (Replicate provider, added 2026-08-14) says "Replicate non_video_in tiers: 480p $0.04/s, 720p $0.09/s". Still secondary. | [POLL] https://github.com/pollinations/pollinations/blob/main/shared/registry/image.ts |
| C20 | §5.7 / §7.2: ElevenLabs policy on minor voices UNVERIFIED | Field report: "ElevenLabs Voice Design refuses a voice that reads as a child." | [VSB-V] (Oct 2026) |
| C21 | §5.1: v4 keeps the native accent | Confirmed, with the converse added. When the output language differs from the voice's source language, v4 "aims for fluent, natural-sounding speech in the target language rather than carrying over the reference accent." **An English-source designed voice will not reliably sound Mexican.** v4's Spanish is listed as "Spanish, LatAm (spa)". | [EL-V4CAP]; [EL-MODELS] |
| C22 | §1.1: Mini ModelArk ID `dreamina-seedance-2-0-mini-260615` | ComfyUI uses `dreamina-seedance-2-0-mini`, with no date suffix. Minor; check it on ModelArk. | [COMFY] |

## Part 2. Top claims re-verified (status)

| Claim | Status | Evidence |
|---|---|---|
| Slug `bytedance/seedance-2.5`, version `a10a543d…813f`, 13 fields: `prompt`, `image`, `last_frame_image`, `reference_images`≤30, `reference_videos`≤10/30 s, `reference_audios`≤10/30 s, `duration` -1..30, `resolution` 480p/720p, `aspect_ratio` 7 values incl. `adaptive` (default `16:9`), `generate_audio` (default true), `watermark`, `output_format` mp4/mov, `seed` | **VERIFIED** (secondary schema captures) | cortex fixture (fetched today); genfeed field list (captured 2026-10-05) identical; [LV] |
| `bytedance/seedance-2.0`: resolution `480p,720p,1080p,4k`; duration -1..15; refs 9/3/3; aspect ratios include `9:21` | **VERIFIED** | [GFV] 2026-10-05; [RS20] 2026-06-05 (no 4k yet then) |
| Replicate prices: 2.5 $0.1028 / $0.2312 (video input $0.4304 / $0.9676); 2.0 $0.08 / $0.18 / $0.45 / $1.00; 2.0 Fast $0.07 / $0.15 | **VERIFIED** | [GFV]; [CFDOC25] (official, identical for 2.5) |
| No `negative_prompt` on Seedance 2.x (Replicate or Cloudflare) | **VERIFIED** | [RS25]; [CFDOC25]. Note that Veo 3.1 and Kling v3 on Replicate **do** have `negative_prompt` [GFV]. |
| Frame mode and reference mode are mutually exclusive; `reference_audios` needs a reference image or video on Replicate | **VERIFIED** | Schema text [RS25]; [LV] "will 422". Cloudflare 2.5 allows audio-only input [CFDOC25]. |
| Native audio: `generate_audio` defaults to true; dialogue in quotes | **VERIFIED** | [RS25]; [RS20] |
| Faces are blocked on Seedance 2.x input images, including AI-generated faces | **VERIFIED** (C1) | [COMFYPR]; [VSB-S] |
| Prompt cap ≤2000 characters on 2.5 | **VERIFIED** (Cloudflare `maxLength:2000` on both 2.0 and 2.5; [LV] and [NICK] say the Replicate 2.5 limit is 2000) | [CFDOC25]; [LV]; [NICK] |
| Nano Banana Pro fields (`allow_fallback_model` "currently bytedance/seedream-5", `safety_filter_level`, resolution default 2K, 11 aspect ratios); NB2 fields (`google_search`, `image_search`, 15 aspect ratios); **no `seed`** on NB, NB2 or Pro | **VERIFIED** | [L1] (2026-03-06); [PUTER] |
| NB prices: 2.1 $0.0336 / $0.0504 / $0.1134; Pro $0.15 / $0.15 / $0.30; NB2 $0.067 / $0.101 / $0.151; Lite $0.034; NB $0.039 | **VERIFIED** | [GFR] (2026-10-06); [PUTER] |
| 1K pixel sizes (16:9 = 1344×768, etc.) | **VERIFIED** | [COOKBOOK] |
| `eleven_v4`: only `stability` and `similarity_boost`, no `style`/`speed`, no SSML; 10,000-character limit; 90+ languages | **VERIFIED** | [EL-SKILL]; [EL-WHATV4]; [EL-MODELS] |
| Text-to-Dialogue: ≤10 voices, ≤2,000 characters "for reliable generation", `model_id` default `eleven_v3`, `settings{stability,similarity}` | **VERIFIED** | [EL-TTD] mirror |
| Voice Design: `model_id` ∈ {`eleven_multilingual_ttv_v2` (default), `eleven_ttv_v3`}, text 100–1000 characters, `guidance_scale` 5, `loudness` 0.5, `reference_audio_base64`/`prompt_strength` ttv_v3 only | **VERIFIED** (also `quality`, `stream_previews`) | [EL-VD] mirror |
| `sync/lipsync-2-pro` $0.08325 per output second; fields `video`, `audio` (.wav), `sync_mode` enum, `temperature` 0–1 (0.5), `active_speaker` | **VERIFIED** (secondary) | [L2] (2026-09-14); [L1] |

## Part 3. Additions (missing from the guide)

1. **Cloudflare Workers AI is the practical face route, and it is not more expensive** [CFDOC25]:
   - Seedance 2.5 on Cloudflare costs exactly the Replicate price ($0.1028 / $0.2312 per second).
   - The schema adds `use_virtual_avatar` (default false), `fps` (const 24) and `camera_fixed` ("no effect").
   - `aspect_ratio` defaults to `adaptive`; first/last-frame mode forces `adaptive`.
   - `additionalProperties:false`; `prompt` maxLength 2000; audio-only references are allowed.
   - Output is `{"video": url}`.
   - Call it from a Worker: `env.AI.run('bytedance/seedance-2.5', {...})`. The REST path from Python is UNVERIFIED.
   - Seedance 2.0 is cheaper on Cloudflare than on Replicate (C13).
2. **Face-capable I2V alternatives on Replicate.** These accepted photoreal faces in a field run in Oct 2026 [VSB-V]; Spanish speech quality is untested. Schemas and prices are from [GFV] (2026-10-05).

   | Slug | Key fields | Price (Replicate) |
   |---|---|---|
   | `google/veo-3.1` | `image`, `last_frame`, `reference_images`, `duration` ∈ {4, 6, 8}, `resolution` 720p/1080p, `aspect_ratio` 16:9/9:16, `generate_audio`, `negative_prompt`, `seed` | $0.40/s with audio, $0.20/s silent |
   | `kwaivgi/kling-v3-omni-video` | `start_image`, `end_image`, `multi_prompt`, `reference_images`, `reference_video`, `generate_audio` (default false), `mode` standard/pro/4k | standard $0.168 silent / $0.224 audio; pro $0.224 / $0.28; 4k $0.42 |
   | `kwaivgi/kling-v3-video` | adds `negative_prompt` | same tiers |
   | `prunaai/p-video` | `image` + `audio` input (an ElevenLabs line drives the clip), `draft` | 720p $0.02/s, draft $0.005/s |
3. **ModelArk virtual library as an automated route.** ComfyUI uploads every first frame and reference to a per-customer "Seedance virtual library" (`/proxy/seedance/virtual-library/assets` → poll until `Active` → `asset://<id>`) and then sends `role:"first_frame"`. Whether that keeps the exact opening frame, unlike the Cloudflare flag, is UNVERIFIED. ark-mcp PR #74 (2026-09-24) also adds real-person verification tools to the asset library [COMFY][ARK74].
4. **2.5 keyframe mode, for strict alignment in reference mode** [SD25G mirror §5]:
   - Open the prompt with "Use Images 1 to N in order as keyframes."
   - Storyboard grids are only loosely followed.
   - There are two first-frame routes. `role=first_frame` lands exactly and locks the ratio. A reference image named "Image 1 is the first frame" is approximate and leaves the ratio free [SD25SPEC].
5. **2.5 locked vs unlocked tasks and trigger words** [SD25G mirror §2][SD25SPEC]:
   - Editing needs a trigger word (edit video, add, insert, remove, delete, modify, replace, change to), `duration:-1` and `adaptive`.
   - Extension needs a trigger (extend forward, extend backward, continue, continue from, extend the story).
   - Edited output may differ by ≤0.3 s, or by 0 s if the source was made by 2.5.
6. **2.5 input facts** [SD25G mirror]:
   - Any input-driven ratio in [0.4, 2.5].
   - Reference images up to 4K.
   - Recommended 1–8 image subjects; 9–12 possible but less stable.
   - "When a reference is accurate enough, do not describe the scene again."
7. **sd25-pe dialogue rules** [SD25PE l.829, l.935]:
   - Never invent an accent.
   - Never let the model infer Mandarin; name the spoken language explicitly per line.
   - Restate "no subtitles" whenever subtitles are not wanted.
8. **ElevenLabs v4 details** [EL-BP][EL-V4CAP]:
   - A tag can be read as an SFX request; write voice-quality tags such as `[low, gravelly voice]`.
   - v4 understands IPA between slashes.
   - v3 and v4 do not support SSML `<break>`.
   - Voice Design voices "may not be as performative" on v4.
   - Behaviour may shift over time.
9. **Replicate 2.5 metrics and seed** [RIFF]:
   - Metrics include `model_variant`, `resolution_target`, `token_output_count` and `video_output_duration_seconds`.
   - When no seed is set, it can be recovered from the logs ("Using seed: N").
10. **QC for audio:** clips can come back with no audio stream. Run `ffprobe -v error -select_streams a -show_entries stream=codec_name,duration -of csv=p=0 clip.mp4` on every take [VSB-V].
11. **Nano Banana 2.1 on fal takes `seed` and a thinking level** (fal charges +$0.002 for "high"). If reproducible reference stills matter, fal is the seeded route; Replicate has no known seed field (FIELD; sonerady/dires-server code).
12. **Other 2026 video models seen but not evaluated** [POLL]: MiniMax H3 (stereo audio, 2K, 4–15 s), Wan 3.0, Gemini Omni 1.1 Flash (Vertex), Grok Imagine Video 1.5, HappyHorse 1.1.

---

## Part 4. Full corrected guide

# serie-factory: build guide for the prompt generator (Seedance, Nano Banana, ElevenLabs, lip-sync), as of 2026-10-07 (fact-checked)

**How to read this.** This merges five research reports, followed by a fact-check pass on 2026-10-07. Corrections are marked **[FC]**.

Most primary domains were blocked: replicate.com, docs.byteplus.com, ai.google.dev, elevenlabs.io, x.com, seed.bytedance.com and fal.ai. So most facts come from:
- verbatim mirrors of official material on GitHub;
- **Cloudflare's official model catalog** (cloudflare-docs, which serves the same Seedance models) **[FC]**;
- third-party captures of Replicate `openapi_schema` pages;
- dated practitioner repos and write-ups.

Source keys such as **[RS25]** point to Appendix B. Evidence tiers:
- **OFF**: official ByteDance, BytePlus, Google, ElevenLabs or Cloudflare material, including verbatim mirrors.
- **SCHEMA**: a captured provider input schema.
- **FIELD**: practitioner reports.
- **UNVERIFIED**: not confirmed. The marker sits on the claim itself.

**One rule overrides everything here.** At startup, call `GET https://api.replicate.com/v1/models/{owner}/{name}` and read `latest_version.openapi_schema`. Validate every payload against it before you submit. These schemas changed during 2026; for example, `4k` was added to Seedance 2.0's resolution enum between 2026-06-05 and 2026-09 [RS20][ADTOOL][GFV]. For Cloudflare, validate against the catalog schema, which rejects unknown keys (`additionalProperties:false`) [CFDOC25] **[FC]**.

---

## 1. Model landscape (Oct 2026)

### 1.1 Seedance versions that exist

"Seedance 2.5" is real. No Seedance 3 has been announced, there is no "2.1", and no "2.5 Fast/Pro" slug was found on Replicate **[FC: GitHub code search 2026-10-07]**.

| Version | Release | ModelArk ID | Replicate slug | Duration | Resolution (Replicate / Cloudflare) | Audio | Refs |
|---|---|---|---|---|---|---|---|
| 1.0 Pro / Pro Fast / Lite | 2025 | `doubao-seedance-1-0-pro-250528`, `…-pro-fast-251015` | `bytedance/seedance-1-pro`, `-1-pro-fast`, `-1-lite` | 2–12 s | ≤1080p | none | Lite: 1–4 images (UNVERIFIED) |
| 1.5 Pro | 2025-12-23 | `seedance-1-5-pro-251215` | `bytedance/seedance-1.5-pro` | 2–12 s | ≤1080p | yes, default `false` | first/last frame only |
| 2.0 | China launch 2026-02-10 or 02-12; on Replicate from 2026-04-08 [RX]; Cloudflare catalog 2026-05-22 [CFDOC20] | `dreamina-seedance-2-0-260128` | `bytedance/seedance-2.0` | 4–15 s or -1 | 480p/720p/1080p/4k | yes | 9 img, 3 vid, 3 aud |
| 2.0 Fast | same ID date | `…-2-0-fast-260128` | `bytedance/seedance-2.0-fast` | 4–15 s | 480p/720p | yes | same as 2.0 |
| 2.0 Mini | ≈2026-06-22; Replicate by 2026-08-14 [POLL] | `dreamina-seedance-2-0-mini` (ComfyUI) or `…-mini-260615` (UNVERIFIED) **[FC]** | `bytedance/seedance-2.0-mini` | 4–15 s (UNVERIFIED) | 480p/720p ("up to 720p" [ADTOOL]) | yes | UNVERIFIED |
| **2.5** | Apps 2026-07-31; API 2026-08-07 [TECHNODE][EVOLINK][SEEDBLOG]; Cloudflare catalog 2026-08-07 [CFDOC25] | `dreamina-seedance-2-5-260628` | `bytedance/seedance-2.5` | **4–30 s** or -1 | **480p/720p only** (Replicate and Cloudflare); **ModelArk also 1080p** **[FC]** | yes | 30 img (≤4K each), 10 vid (≤30 s), 10 aud (≤30 s) |

Sources for the table: [ARKAPI][COMFY][TAPC][RS25][RS20][TREG][GFV][EMILY][CFDOC25].

Notes on the table:
- **Replicate date for 2.5 is UNVERIFIED.** The pollinations registry addedDate is 2026-08-09 [POLL]; cellcog has it by 2026-08-22 [CELLCOG]; Cloudflare's catalog entry was created 2026-08-07 [CFDOC25].
- **Frame rate:** fixed at 24 fps (`fps` is const 24 on Cloudflare). No CFG, steps or sampler controls are exposed anywhere [COMFY][ARKAPI][CFDOC25].
- **ByteDance's own framing of 2.5:** "not a generational leap" over 2.0. It hardens 2.0 for production work: longer clips, more references, more stable edit and extend, MOV output [SD25G].
- **What 2.5 adds over 2.0** [SD25G §6]:
  - It responds to integer-second timestamps; 2.0 responds to shot numbers only.
  - Multi-view subject images are supported (discouraged on 2.0).
  - Any input-driven ratio in [0.4, 2.5].
  - MOV output for edit and extend.
- **Keep a separate prompt profile per version.** Practitioners report that "prompts that worked well on the previous model produce broken, glitchy output on 2.5" [MINDST].

**Conflicts (flagged):**
- **2.5 at 1080p [FC].**
  - Replicate and Cloudflare: 480p/720p only [RS25][GFV][CFDOC25].
  - ModelArk: ComfyUI's ModelArk nodes (fetched 2026-10-07) offer `480p/720p/1080p` for 2.5, and a **Draft → 1080p final** path [COMFY]. ark-mcp PR #83 (2026-10-03) says the same, plus an internal "2.5 Premium" with a 4K final that is "not in the public guide" [ARK83].
  - The 2026-08-09 spec digest ("no path above 720p") predates this.
  - Native or upscaled: UNVERIFIED. [ANIL] says upscaled.
  - **On Replicate, 720p is the maximum.**
- **Audio channels.** The ModelArk doc says mono; the Seed page says stereo [ARKAPI] (UNVERIFIED).
- **Spanish support.**
  - The official 2.5 guide mirror says "Native generation in **10+ languages**" without a list [SD25G mirror]. The 11-language list EN/ZH/ES/ID/PT/JA/MS/TH/AR/VI/KO is UNVERIFIED **[FC]**.
  - On 2.0, Spanish scored AQ 4.14, AVS (sync) 4.14 and APF 4.00 in developer-run 1–5 evaluations [SD20P via EMILY].

### 1.2 What to use: drafts vs finals

| Stage | (a) Cheap drafts | (b) Finals | Do not use |
|---|---|---|---|
| Video | `bytedance/seedance-2.5`, `resolution:"480p"`, 4–5 s, **$0.1028/s** [GFV][CFDOC25]. Same model and grammar as the final, so the draft really tests the prompt. | `bytedance/seedance-2.5`, `720p`, **$0.2312/s** [GFV][CFDOC25]. For native 1080p or 4K: `bytedance/seedance-2.0` at `1080p` $0.45/s or `4k` $1.00/s on Replicate ($0.37 / $0.78 on Cloudflare) **[FC]**, ≤15 s, 2.0 grammar. | `duration:-1` except for edit or extend, because it bills actual output seconds, up to 30 s. Do not draft on `-2.0-mini` for a 2.5 final: it is a different model with a different grammar. |
| Video, 2.0 profile only | `bytedance/seedance-2.0-fast` 480p, $0.07/s [GFV]. Mini 480p $0.04/s [POLL] (secondary). Fast reportedly ignores multi-shot, slow motion and dolly moves more often [FIELD, prompting report via fal]. | | |
| **Faces in start frames [FC]** | **Replicate: face-free or face-light frames only** (back, profile-in-shadow, silhouette, hands, wide shots with small faces). Photoreal faces, AI-made ones included, are refused [VSB-S][COMFYPR]. | (1) Cloudflare `use_virtual_avatar:true`: AI-made faces passed in a 2026-10-07 field test, but the start frame becomes approximate [VSB-S]. (2) ModelArk virtual library `asset://` [COMFY][BPASSET]. (3) Another I2V model that accepts faces: `google/veo-3.1` or `kwaivgi/kling-v3-omni-video` [VSB-V][GFV]. | Moderation-evasion overlays |
| Identity refs (stills) | `google/nano-banana-2.1` 1K, **$0.0336** [GFR] | `google/nano-banana-pro` 2K **$0.15** or `nano-banana-2.1` 2K **$0.0504**. A/B these on the first character [GFR]. | `google/nano-banana` (Gemini API shutdown 2026-10-02) and `google/nano-banana-2` (Gemini API shutdown 2026-10-29). Vertex keeps them until 2027-03-15 and 2027-05-28; what Replicate does is UNVERIFIED [LITELLM] **[FC]**. |
| Start frames | `nano-banana-2.1` 1K | `nano-banana-2.1` 2K for up to 4 characters (UNVERIFIED cap); `nano-banana-pro` for 5 people [NB21][GCBP] | |
| Local still fixes | `black-forest-labs/flux-kontext-pro` $0.04 (has `seed`); `ideogram-ai/ideogram-character` with `image`+`mask` inpainting [RPUB][PUTER] | same | |
| Voice | `eleven_v4` (cost is negligible, so drafts and finals use the same model) | `eleven_v4`. Fallbacks: `eleven_v3` (no request stitching **[FC]**), then `eleven_multilingual_v2` [EL-V4][EL-SKILL][EL-STITCH] | `eleven_flash_v2_5` for drama; `eleven_turbo_v2_5` is superseded by Flash [EL-MODELS] |
| Voice casting | `eleven_ttv_v3` (Voice Design) [EL-VD] | same | |
| Lip-sync | Skip, or use `sync/lipsync-2` (Replicate price UNVERIFIED) | `sync/lipsync-2-pro` **$0.08325 per output second** (verified 2026-09-14) [L2] | |

**Draft-to-final reproducibility.**
- Seeds give "the same neighbourhood", not identical output, and changing resolution changes the result even with the same seed [ANIL].
- The only true draft-then-final path is **2.5 Draft mode on ModelArk**: `draft: true` returns a 480p preview and a `draft_task_id`. The final render is 1080p and reuses the draft's prompt, refs, duration, ratio and audio setting, within 7 days [ARK83][COMFYDOC][COMFY].
- **There is no `draft` field in the Replicate or Cloudflare 2.5 schemas** [RS25][CFDOC25]. On those routes a draft validates the prompt, not the exact take.

### 1.3 Replicate Seedance input schemas (exact)

#### `bytedance/seedance-2.5` (version `a10a543dffa352140391fc66d360fe2ed5a78a9c8f8d3d7cf07548b9e312813f`) [RS25][GFV]

Field list re-confirmed against the 2026-10-05 capture **[FC]**.

| Field | Type | Default | Allowed values | Schema text / notes |
|---|---|---|---|---|
| `prompt` | string | `""` | No maxLength in the Replicate schema. **Keep ≤2000 characters**: Cloudflare caps at 2000 [CFDOC25]; Replicate users report a hard 2000-character limit [NICK][LV]. | "Optional when a media input… is supplied. Seedance 2.5 works best with detailed, structured 'production brief' style prompts." |
| `image` | uri, nullable | – | – | "First-frame image… **Cannot be combined with reference images, videos, or audios.**" |
| `last_frame_image` | uri, nullable | – | – | "Requires a first-frame image. Cannot be combined with reference images, videos, or audios." |
| `reference_images` | uri[] | `[]` | ≤30 | "Reference them in your prompt as [Image1], [Image2], etc." |
| `reference_videos` | uri[] | `[]` | ≤10, combined ≤30 s | "motion transfer, style reference, editing, and extension… [Video1]". **Moves billing to the video-input tier (4.2×).** |
| `reference_audios` | uri[] | `[]` | ≤10, combined ≤30 s | "for audio-driven generation and lip-sync. **Requires at least one reference image or video.**" |
| `duration` | int | 5 | -1..30. The live API accepts 4–30 or -1. | "-1 for intelligent duration… Editing mode requires -1." |
| `resolution` | enum | `720p` | `480p`, `720p` | |
| `aspect_ratio` | enum | `16:9` | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `adaptive` (no `9:21`) | "First/last-frame, editing, and extension modes require 'adaptive'." |
| `generate_audio` | bool | `true` | | "dialogue (use double quotes in prompt), sound effects, and background music" |
| `watermark` | bool | `false` | | |
| `output_format` | enum | `mp4` | `mp4`, `mov` | Use `mov` for edit and extend chains [SD25G] |
| `seed` | int, nullable | – | | "Reproducibility is not guaranteed." |

Notes:
- **Not in the schema:** `negative_prompt`, `fps`, `camera_fixed`, `draft`, `return_last_frame`, `use_virtual_avatar`, `last_image`.
- **Output:** a single URI string.
- **Live behaviour [RIFF, 2026-08-29]:**
  - I2V with `aspect_ratio:"16:9"` was accepted. **[FC]** The input frame was itself 16:9, so this proves acceptance only; keep sending `adaptive`.
  - T2V at 480p and 1:1 gave 640×640 at 24 fps; I2V of a 1280×720 frame gave 854×480.
  - Metrics include `model_variant`, `resolution_target`, `token_output_count` and `video_output_duration_seconds`.
  - An unset seed is recoverable from the logs ("Using seed: N") **[FC]**.
- **`camera_fixed`:** Cloudflare's 2.5 schema says "Not currently supported by the provider; has no effect" [CFDOC25]. **Write "static locked-off camera" in the prose instead.**

#### Cloudflare Workers AI `bytedance/seedance-2.5` [CFDOC25] **[FC: new]**

- **Same fields as Replicate, plus:**
  - `fps` (const 24);
  - `camera_fixed` (no effect);
  - `use_virtual_avatar` (bool, default false): "Route image reference inputs (image, reference_images, last_frame_image) through ByteDance's trusted virtual avatar asset library before generation. Intended for AI-generated/virtual character avatars that would otherwise be blocked by face or deepfake detection".
- **Differences:**
  - `aspect_ratio` defaults to `adaptive`; first/last-frame forces `adaptive`.
  - `prompt` maxLength 2000.
  - **Audio-only references allowed.**
  - `additionalProperties:false`.
  - Output is `{"video": url}`.
- **Price:** identical to Replicate.
- **Field caveat with `use_virtual_avatar:true`** [VSB-S, 2026-10-07]: "`image` guides the face only and does not fix the opening shot". 2.0 and 2.0 Fast cap at 12 s. Set it only for AI-made people whose rights you hold.

#### `bytedance/seedance-2.0` [RS20 2026-06-05][TREG 2026-09-01][GFV 2026-10-05]

| Field | Type | Default | Allowed values | Notes |
|---|---|---|---|---|
| `prompt` | string, required | – | **maxLength 4000** (2026-06 snapshot; Cloudflare caps at 2000) | "BytePlus recommends keeping prompts under 600 English words." |
| `image` | uri | – | – | First frame. "Cannot be combined with reference images." |
| `last_frame_image` | uri | – | – | "Only works if a first frame image is also provided." |
| `reference_images` | uri[] | `[]` | ≤9 | `[Image1]`… |
| `reference_videos` | uri[] | `[]` | ≤3, ≤15 s total | `[Video1]` |
| `reference_audios` | uri[] | `[]` | ≤3, ≤15 s total | "Requires at least one reference image or video." `[Audio1]` |
| `duration` | int | 5 | -1..15. The live API rejects <4: "Duration must be between 4 and 15 seconds, or -1". | |
| `resolution` | enum | `720p` | `480p`, `720p`, `1080p`, `4k` (4k added after 2026-06-05; confirmed 2026-10-05) | "4K outputs 10-bit H.265/HEVC" |
| `aspect_ratio` | enum | `16:9` | `16:9`, `4:3`, `1:1`, `3:4`, `9:16`, `21:9`, `9:21`, `adaptive` | Send `adaptive` with `image`, or the output defaults to 16:9 [BACKLOT] |
| `generate_audio` | bool | `true` | | |
| `seed` | int, nullable | – | | |

Notes:
- No `fps`, `camera_fixed` or `watermark`.
- **Conflict on reference images.** A search summary claims 2.0 `reference_images` takes 1–4 images and "cannot be used with 1080p" [weaknesses report, UNVERIFIED]. The schema says ≤9, with no 1080p restriction [RS20][ADTOOL].
- **`image` plus `reference_audios` on 2.0 is UNVERIFIED.** Audio requires a reference image or video, and `image` excludes reference images. Whether `image + reference_videos + reference_audios` is accepted is untested.

#### `bytedance/seedance-2.0-fast`
Same fields as 2.0, except `resolution` is `480p` or `720p` only; sending 1080p returns 422 [JUSPAY 2026-07-19][GFV].

#### `bytedance/seedance-2.0-mini`
No Replicate schema capture was found (**UNVERIFIED**). Sources conflict:
- One app config lists 480p/720p, duration -1..15, `adaptive`, and ≤3 reference audios.
- Visualsandbox reports "4–12 s, no adaptive, one ref video + one ref audio" on its own route [VSB].
- AtlasCloud lists 6 img + 3 aud + 3 vid [ATLASMINI].
- The Cloudflare catalog has the model, with `use_virtual_avatar` [CFCAT].

#### Fallbacks (1.x) [TREG]
- **`seedance-1-pro`:** `prompt`*, `image`, `last_frame_image`, `duration` 2–12, `resolution` (default 1080p), `aspect_ratio` ("Ignored if an image is used"), `fps` 24, **`camera_fixed`**, `seed`.
- **`-1-pro-fast`:** the same, without `last_frame_image`.
- **`seedance-1.5-pro`:** adds `generate_audio` (default `false`).
- **Multi-shot on 1.0 Pro:** "`… lens switch to …`", with 2–3 switches per clip [SD10G].
- **Faces:** 1.x reportedly flags fewer people scenes than 2.0 [BACKLOT] (UNVERIFIED).

#### Face-capable I2V alternatives on Replicate [GFV 2026-10-05][VSB-V] **[FC: new]**

| Slug | Fields | Price | Face/policy |
|---|---|---|---|
| `google/veo-3.1` | `prompt`, `image`, `last_frame`, `reference_images`, `duration` ∈ {4, 6, 8} (default 8), `resolution` 720p/1080p, `aspect_ratio` 16:9/9:16, `generate_audio` (default true), `negative_prompt`, `seed` | $0.40/s with audio, $0.20/s silent | Photoreal faces accepted in a field run (Oct 2026). Reference images only at 16:9 and 8 s; `last_frame` ignored when reference images are set [VSB-V]. |
| `kwaivgi/kling-v3-omni-video` | `prompt`, `start_image`, `end_image`, `reference_images`, `reference_video`, `multi_prompt`, `duration`, `aspect_ratio`, `generate_audio` (default false), `mode` standard/pro/4k, `keep_original_sound`, `video_reference_type` | standard $0.168/s silent, $0.224/s audio; pro $0.224 / $0.28; 4k $0.42 | Faces accepted (field). Audio is exclusive with `reference_video`; 4K excludes `reference_video` [ADTOOL]. |
| `kwaivgi/kling-v3-video` | as above minus references, plus `negative_prompt` | standard $0.168 / $0.252; pro $0.224 / $0.336 | UNVERIFIED |
| `prunaai/p-video` | `image`, `audio`, `prompt`, `duration`, `resolution`, `draft`, `last_frame_image`, `seed`, `disable_safety_filter` | 720p $0.02/s (draft $0.005); 1080p $0.04/s | Faces accepted (field); an audio track sets the length [VSB-V] |

Spanish speech quality and horror moderation on all four are UNVERIFIED.

### 1.4 Hard rules for every Seedance 2.x call (encode as validators)

1. **Photoreal human faces in any input image are rejected, including AI-generated ones. [FC: upgraded from "likely"]**
   - **Official statement (ModelArk wording):** "2.x models do not support directly uploading reference images or videos that contain real human faces" [BPASSET via reports][ARCREEL 2026-08-31][OPENSTORY 2026-09-29].
   - **Error codes:**
     - ModelArk: `InputImageSensitiveContentDetected.PrivacyInformation` (HTTP 400; "7003 PrivacyInformation" [VIVI]).
     - Replicate: `E005 "The input or output was flagged as sensitive"`.
     - Cloudflare: "may contain real person".
   - **ComfyUI's shipped hint:** "Seedance blocks realistic human faces, even AI-generated ones. Try an image without one or a stylized character, or check your prompt" [COMFYPR 2026-09-30].
   - **Latest field test [VSB-S, 2026-10-07, Seedance 2.5]:** "without the flag, the portrait and every character sheet with a face were refused on both providers. A sheet with no face passed, but the model made up a new face. With the flag, the portrait passed as a reference and as a start frame, and the face matched in every frame."
   - **Earlier evidence:**
     - Frontal and close-up faces gave E005 while profile, partial-face and from-behind shots passed (seedance-2.0) [ZEKE].
     - Synthetic faces gave E005 on 2.5 [NICK 2026-09-05].
     - A face shot gave E005 while a hands-only insert passed [ATHA].
     - No face passes on fal 2.5, not even frames from Seedance's own output; stylized 3D faces pass [RECOUP 2026-09-14].
   - **T2V without an input image generates people without problems** [REALAMAN].
   - **Sanctioned routes:**
     - **Cloudflare Workers AI `use_virtual_avatar: true`** on `bytedance/seedance-2.0/-2.0-fast/-2.0-mini/-2.5` [CFDOC25][CFCAT].
       - Field-verified pass for AI-made photoreal faces (2026-10-07) [VSB-S].
       - The start frame becomes approximate ("guides the face only").
       - Requires an AI-made, rights-cleared person.
       - Same price as Replicate for 2.5.
     - **ModelArk private virtual-portrait asset library:** `CreateAsset` → poll `GetAsset` until `Active` → `asset://<id>`.
       - ComfyUI automates this per customer for every frame and reference [COMFY].
       - Advanced Creation Rights are needed for the private library; a real-person verification flow also exists [BPASSET][ARK74 2026-09-24].
       - Whether `role:first_frame` + `asset://` keeps the exact opening frame is UNVERIFIED.
     - Seedream 5.0 text-to-image outputs are trusted for 30 days on the same ModelArk account [MOKU #21] (**UNVERIFIED**; does not work through resellers).
     - **Non-Seedance I2V** for face shots: Veo 3.1 or Kling v3 Omni on Replicate (§1.3).
   - **Continuity consequence:** chaining the last frame of a clip that shows a face is also rejected [RECOUP].
2. **Frame mode and reference mode cannot be mixed in one call.** Frame mode is `image` (+ optional `last_frame_image`). Reference mode is any of `reference_images`, `reference_videos` or `reference_audios` [RS25][RS20]. Violations return 422 or E006 [LV][VSB-S]. So "start frame + character sheets + ElevenLabs line" is **impossible in one Replicate call**.
3. **`reference_audios` needs at least one reference image or video on Replicate.** Audio alone fails with E006 [A1]. Audio-only input works on ModelArk and Cloudflare 2.5 [CFDOC25].
4. **`aspect_ratio:"adaptive"` is required** for first/last-frame, edit and extend modes [RS25].
5. **Duration:** 4–15 s (2.0) or 4–30 s (2.5). Use -1 only for edit and extend, which require it.
6. **Input limits (ModelArk docs; Replicate passes them through, but whether it adds limits of its own is UNVERIFIED)** [ARKAPI][SD25G]:
   - Images: jpeg/png/webp/bmp/tiff/gif/heic; aspect ratio 0.4–2.5; 300–6000 px per side; <30 MB each; ≤64 MB per request.
   - Reference videos: mp4/mov, 2–15 s each (2–30 s on 2.5), 24–60 fps, ≤200 MB.
   - Reference audio: wav/mp3, 2–15 s each (2–30 s on 2.5), ≤15 MB.
   - **First and last frames must share the ratio.** **[FC]** The 2.5 guide says a mismatched last frame "gets stretched"; the ModelArk API doc says it is centre-cropped (conflict).
   - Inputs around 1536 px wide correlated with E005, while around 768 px passed [AIMV] (UNVERIFIED).
7. **Never send keys that are not in the schema.** Cloudflare rejects them (`additionalProperties:false`) [CFDOC25] **[FC]**. Replicate behaviour is UNVERIFIED: one report says unknown keys error [BACKLOT], another says they are silently dropped [MOTIONMAX].

### 1.5 Prices (USD per output second)

"With video input" means `reference_videos` are attached. Images, audio and `generate_audio` do not change the rate [AUTOSHOW][RIFF].

| Model | 480p | 720p | 1080p | 4k | With video input | Source |
|---|---|---|---|---|---|---|
| seedance-2.5 (Replicate = Cloudflare) | 0.1028 | 0.2312 | – | – | 0.4304 / 0.9676 | [GFV 2026-10-05][CFDOC25] |
| seedance-2.0 (Replicate) | 0.08 | 0.18 | 0.45 | 1.00 | 0.10 / 0.22 / 0.55 / 1.25 | [GFV] |
| seedance-2.0 (Cloudflare) **[FC]** | 0.07 | 0.15 | 0.37 | 0.78 | 0.172 / 0.372 / 0.914 / 1.866 | [CFDOC20] |
| seedance-2.0-fast (Replicate) | 0.07 | 0.15 | – | – | 0.08 / 0.17 | [GFV] |
| seedance-2.0-mini (Replicate) | 0.04 | 0.09 | – | – | ? | [POLL] (secondary) **[FC]** |

Other routes, for comparison only: fal 2.5 $0.473/s; Runway `seedance2_5` $0.30/s [LITELLM]. Volcengine Ark (mainland China) reports about ¥11 per 10 s at 720p with audio [RESCI 2026-09-25] (UNVERIFIED).

**[FC]** The May 2026 figure $0.07/$0.15 for 2.0 [MAJIK] matches Cloudflare's current 2.0 price. It is a provider or time difference, not a typo. Read the live price before budgeting.

**Worked example** (2.5, 60 shots × 5 s per episode):
- One 720p pass ≈ $69. Three takes per shot ≈ $208.
- 480p drafts at 4 s × 2 ≈ $49 [weaknesses report].
- Practitioners report a keep rate of about 25%, i.e. 3–4 takes per kept shot [CSARKO 2026-09-16] (UNVERIFIED).

### 1.6 Replicate operations

- **Input files:** a public URL, a client upload (≤100 MB), or a data URI (only below 1 MB) [RDOCS]. Replicate's own `api.replicate.com/v1/files/...` URLs reportedly fail as Seedance inputs because they need auth [CLSAND] (UNVERIFIED). **Use publicly fetchable URLs.**
- **Output:** files on `replicate.delivery` expire after **1 hour**, and API predictions are deleted after 1 h. Download immediately [RDOCS] (not re-checked: domain blocked).
- **Rate limits:** 600 prediction creates per minute; HTTP 429 when throttled [RDOCS].
- **Latency:**
  - 2.5 at 480p, 4 s clip: 111–151 s [RIFF].
  - 2.5 at 720p, 5 s clip: 322 s [NICK].
  - Budget a 15-minute poll window [MOTIONMAX].
- **Failure triage by timing:** a failure in under 10 s means a filter rejection, so rewrite rather than re-run. A failure after more than 30 s means infrastructure or complexity [HIGGS]. One field skill suggests trying the same inputs on another model before rewriting [VSB-S].
- **Error classes to log:**
  - input-face: E005, `InputImageSensitiveContentDetected.PrivacyInformation`
  - prompt
  - output-video: `OutputVideoSensitiveContentDetected.PolicyViolation`; re-running the same request will not help
  - output-audio: `OutputAudioSensitiveContentDetected.PolicyViolation`, e.g. music copyright [ZJT][COMFY]
  - mode mismatch: E006 / 422; ModelArk `InvalidParameter.TaskTypeConstraint` and `InvalidParameter.TaskTypeMismatch` [COMFY]
  - infra
- **Access:** at the 2.0 launch only Business and Enterprise accounts could run it, in 150+ countries, US excluded [RX 2026-04-08] (could not re-open: x.com blocked). The current rules for 2.5 are **UNVERIFIED**; check the team's account first.
- **Ownership:** Cloudflare acquired Replicate; the deal closed 2025-12-01 [CFACQ]. Cloudflare Workers AI exposes the same models with a 2000-character prompt cap and `use_virtual_avatar` [CFDOC25].
- **Post-processing:**
  - Output may be variable frame rate; normalize with `ffmpeg -r 24 -vsync cfr` [REALAMAN] (UNVERIFIED).
  - Generated audio may end in a click; fade the last ~0.5 s [BDPE troubleshooting A-1].
  - **Check every take for a missing audio stream with `ffprobe`** [VSB-V] **[FC]**.

### 1.7 Nano Banana family and alternatives

**Lifecycle**

| Name | Google API id | Status 2026-10-07 | Replicate slug | Reference caps |
|---|---|---|---|---|
| Nano Banana | `gemini-2.5-flash-image` | Gemini API shutdown **2026-10-02**; Vertex 2027-03-15 [LITELLM]. Replicate page still priced 2026-10-06 [GFR]; serving status UNVERIFIED. | `google/nano-banana` | best with ≤3 images |
| Nano Banana 2 | `gemini-3.1-flash-image` | Gemini API **shutdown 2026-10-29**; **Vertex 2027-05-28** [LITELLM] **[FC]**. Replicate behaviour UNVERIFIED. | `google/nano-banana-2` | up to 14 (6 high-fidelity) [COOKBOOK]; docs: 4 chars + 10 objects; Cloud blog: 5 chars + 14 objects [GCBNB2] (conflict) |
| Nano Banana 2 Lite | `gemini-3.1-flash-lite-image` | released ≈2026-06-30 (Vertex deprecation 2027-06-28 implies GA about 2026-06-28) [LITELLM] | `google/nano-banana-2-lite` | cookbook: **up to 3** [COOKBOOK] |
| **Nano Banana 2.1** | `gemini-nano-banana-2.1` | **GA 2026-10-06** [NB21][NBCARD][NB21NEWS]; on Replicate (priced 2026-10-06) [GFR] | `google/nano-banana-2.1` | 14 total: **≤4 characters + ≤10 objects** (UNVERIFIED, SE only); thinking minimal/medium(default)/high (Google API) |
| **Nano Banana Pro** | `gemini-3-pro-image` (GA 2026-05-28; `-preview` shut down 2026-06-25) [LITELLM] | GA | `google/nano-banana-pro` | 14 total, 6 high-fidelity [COOKBOOK]; "≤5 humans" UNVERIFIED **[FC]** |

Notes:
- **Known 2.1 limitations** per its model card: "Character consistency is not always perfect"; left/right confusion; small text blurry at 1K [NBCARD] (SE).
- **Model ID conflict:** the cookbook still names Pro `gemini-3-pro-image-preview` [COOKBOOK]. Use `gemini-3-pro-image`.

**`google/nano-banana-pro`** [L1 2026-03-06; PUTER 2026-10; TREGNB 2026-09-14]

| Field | Type | Default | Allowed values |
|---|---|---|---|
| `prompt` | string, required | – | – |
| `image_input` | uri[] | `[]` | up to 14 |
| `aspect_ratio` | enum | `match_input_image` | `match_input_image, 1:1, 2:3, 3:2, 3:4, 4:3, 4:5, 5:4, 9:16, 16:9, 21:9` |
| `resolution` | enum | `2K` | `1K, 2K, 4K` |
| `output_format` | enum | `jpg` | `jpg, png` |
| `safety_filter_level` | enum | `block_only_high` | `block_low_and_above`, `block_medium_and_above`, `block_only_high` |
| `allow_fallback_model` | bool | `false` | "Fallback to another model (currently bytedance/seedream-5) if Nano Banana Pro is at capacity". **Keep `false`**, or Seedream silently makes your identity image. |

Notes:
- Output is a single URI.
- **No `seed`, no `negative_prompt`, no thinking control** (verified for NB, NB2 and Pro).
- `match_input_image` needs `image_input`, so always set an explicit ratio [TREGNB].
- Image URLs must return raw bytes with an `image/*` content-type [TREGNB].

**`google/nano-banana-2.1`.** **[FC] The exact Replicate schema is UNVERIFIED; no capture was found, and Puter has no entry.** The likely shape, extrapolated from NB2's Replicate schema [L1][PUTER]:
- `prompt`, `image_input` (≤14), `aspect_ratio` (default `match_input_image`; NB2's enum is `1:1, 1:4, 1:8, 2:3, 3:2, 3:4, 4:1, 4:3, 4:5, 5:4, 8:1, 9:16, 16:9, 21:9`), `resolution` (`1K` default, `2K`, `4K`), `google_search` (bool, false), `image_search` (bool, false), `output_format` (`jpg` default / `png`).
- Whether `thinking_level`, `seed` or a safety field exists on Replicate is **UNVERIFIED**. On fal, 2.1 accepts `seed`, and a "high" thinking level costs +$0.002 per image (FIELD).
- **Always send `google_search:false, image_search:false`** if present. Image Search grounding "find[s] web images as visual context" and could pull web faces into identity [L1].

**`google/nano-banana-2-lite`:** `prompt`, `image_input`, `aspect_ratio`, `output_format`; no resolution field [PUTER].

**Image prices** [GFR, verifiedAt 2026-10-06; PUTER]:

| Slug | 1K | 2K | 4K |
|---|---|---|---|
| nano-banana-2.1 | $0.0336 | $0.0504 | $0.1134 (Google direct 1K $0.0336 [LITELLM]; Google 4K $0.0756 is a conflict) |
| nano-banana-pro | $0.15 | $0.15 | $0.30 (Google direct: $0.134 at 1K/2K, $0.24 at 4K) |
| nano-banana-2 | $0.067 | $0.101 | $0.151 |
| nano-banana-2-lite | $0.034 | – | – |
| nano-banana (legacy) | $0.039 | – | – |

**Alternatives with exact fields** [RPUB][PUTER][APPIFY]. Prices from [PUTER] are UNVERIFIED against replicate.com.

| Slug | Price | Key fields | Use |
|---|---|---|---|
| `bytedance/seedream-5-pro` (2026-07-08) | $0.045 1K / $0.09 2K | `prompt`, `image_input`, `size` 1K/2K, `aspect_ratio`, `output_format` png/jpeg. **No seed.** | Spanish prompts officially supported |
| `bytedance/seedream-4.5` | $0.04 | `image_input` 1–14, `size` 2K/4K, `sequential_image_generation`, `max_images` (1–15), `disable_safety_checker` | batches of related views (consistency UNVERIFIED) |
| `black-forest-labs/flux-kontext-pro` / `-max` | $0.04 / $0.08 | `input_image` (single), `aspect_ratio`, **`seed`**, `safety_tolerance` 0–6 (**max 2 with input images**), `prompt_upsampling` | seeded local edits |
| `black-forest-labs/flux-2-pro` / `-max` / `-flex` / `-dev` | per MP | `input_images` (8/8/10/4), `resolution` (≤2048²), **`seed`**, `safety_tolerance` 1–5; flex adds `steps`, `guidance`, `prompt_upsampling` (default true: turn it off) | seeded multi-ref |
| `ideogram-ai/ideogram-character` | $0.10 / 0.15 / 0.20 | `character_reference_image` (exactly 1), `style_type:"Realistic"`, `magic_prompt_option:"Off"`, **`seed`**, `image` + `mask` | inpaint one stubborn character |
| `qwen/qwen-image-edit-2511` | ≈$0.03 | `image[]` (best 1–3), **`seed`**, `aspect_ratio` (6 values) | cheap two-person fusion [QWEN] |

### 1.8 ElevenLabs and lip-sync APIs

**TTS models** [EL-MODELS][EL-V4][EL-WHATV4][S17 2026-10-02]

| `model_id` | Character limit | Languages | API list price per 1K characters | Notes |
|---|---|---|---|---|
| **`eleven_v4`** | 10,000 | 90+, list includes **"Spanish, LatAm (spa)"** | $0.08 (**UNVERIFIED**; LiteLLM lists v3 and v2 at $0.18 [LITELLM]) **[FC]** | Released in the 2026-09-28 changelog; default in official skills since 2026-10-05 [EL-SKILL]. "Behavior may shift over time." Works with TTS and Text-to-Dialogue; not on the `stream-input` WebSocket. |
| `eleven_v4_turbo` | 10,000 [S19] | 90+ | $0.04 (UNVERIFIED) | real-time, via the Text-to-Dialogue WebSocket |
| `eleven_v3` | 5,000 | 70+ | (UNVERIFIED) | "previous generation"; **no request stitching** [EL-STITCH] **[FC]** |
| `eleven_multilingual_v2` | 10,000 | 29, "Spanish (Spain, Mexico)" | (UNVERIFIED) | most stable; **no tags** |
| `eleven_flash_v2_5` | 40,000 | 32 | $0.04 | numbers not normalized by default |

The v4 launch promo is reported at conflicting rates until 2026-10-12 [S16][S17] (UNVERIFIED).

**`POST /v1/text-to-speech/{voice_id}`** (or `/with-timestamps`, which adds `alignment` with per-character start and end times) [EL-API][EL-TS]

| Field | Values |
|---|---|
| `text` | required |
| `model_id` | default `eleven_multilingual_v2`. **Always set it explicitly.** |
| `language_code` | ISO 639-1 (`"es"`). "**Not supported for multilingual_v2.**" Send it to v3, v4 and Flash only; unsupported codes are ignored. |
| `voice_settings` | `stability` (0.5), `similarity_boost` (0.75), `style` (0), `speed` (1.0; product range 0.7–1.2), `use_speaker_boost` (true) |
| `seed` | 0–4294967295, best effort |
| `previous_text` / `next_text` | context for joins |
| `previous_request_ids` / `next_request_ids` | up to 3 each. **[FC]** Stitching is shown with `eleven_v4` and is "not available for the `eleven_v3` model". If both `previous_text` and `previous_request_ids` are sent, `previous_text` is ignored [EL-STITCH][EL-API]. |
| `pronunciation_dictionary_locators` | up to 3 |
| `apply_text_normalization` | `auto` (default), `on`, `off` |
| query `output_format` | default `mp3_44100_128`. `mp3_44100_192` needs Creator or higher. **WAV/PCM 44.1 kHz needs Pro.** |
| response headers | `request-id`, `history-item-id`, **`character-cost`** [S24] |

Per-model support:
- **v4 accepts only `stability` and `similarity_boost`**: no `style`, no `speed`, no SSML [EL-SKILL][EL-WHATV4]. Send only those two. Whether v4 rejects or ignores the others is UNVERIFIED; one client logs them as "ignored" [S25].
- **v3 `stability` accepts only 0.0, 0.5 or 1.0.** Any other value returns 400 "Invalid TTD stability value" [S21].

**Text-to-Dialogue: `POST /v1/text-to-dialogue/with-timestamps`** [EL-TTD] (re-verified **[FC]**)
- Body: `inputs[{text, voice_id}]`, `model_id` (**the API default is `eleven_v3`, so set `eleven_v4`**), `language_code`, `settings{stability (0.5), similarity (0.75)}`, `seed`, `pronunciation_dictionary_locators`, `apply_text_normalization`, `use_pvc_as_ivc`, `output_format`.
- Limits: **≤10 unique voices**, and **≤2,000 characters** per request "for reliable generation".
- Returns `voice_segments[]` with `start_time_seconds`, `end_time_seconds` and `dialogue_input_index`.

**Lip-sync on Replicate** [L1][L2][L4]

| Slug | Inputs | Price | Notes |
|---|---|---|---|
| **`sync/lipsync-2-pro`** | `video` (mp4), `audio` (wav), `sync_mode` ∈ {`loop` (default), `bounce`, `cut_off`, `silence`, `remap`}, `temperature` 0–1 (0.5, "how expressive"), `active_speaker` bool (false) | **$0.08325/s** (2026-09-14) | Best on teeth and beards. **[FC]** The "deprecated" flag in one catalog is unreliable; still listed by a field skill in October 2026 [VSB-V]. Check the page. |
| `sync/lipsync-2` | same | UNVERIFIED | general default |
| `heygen/lipsync-precision` / `-speed` | `video`, `audio` | UNVERIFIED | |
| `bytedance/omni-human` | `image`, `audio` | $0.14/s | replaces the shot rather than correcting it |
| `kwaivgi/kling-avatar-v2` **[FC]** | portrait + audio | std/pro (UNVERIFIED) | talking head, little body motion [GFV][VSB-V] |

- **[FC] `sync_mode` semantics (schema text):** "Lipsync mode when audio and video durations are out of sync". It only controls length mismatch.
- **[FC] `active_speaker`:** "whoever is speaking in the clip will be used for lipsync".
- **[FC] Input requirement:** lipsync "does not make a still face or a closed mouth talk… a clip with no speaking motion gets no lip movement" (Sync docs, quoted in [VSB-V]).
- **Not on Replicate:** `sync-3` (fal `fal-ai/sync-lipsync/v3`, ≈$0.107–0.133/s). It handles occlusion, profiles and extreme angles [L4][L5], which suits dark, partly hidden horror faces.

### 1.9 Hand-testing parity: make tests match automation

| Surface | Matches the API? | Differences |
|---|---|---|
| **Replicate playground** | **Yes, the source of truth** for the Replicate route. Paste exactly the JSON the pipeline emits. | – |
| **Cloudflare AI Playground / Workers** **[FC]** | Yes, for the Cloudflare route. | Different defaults (`adaptive`), `use_virtual_avatar`, strict schema |
| Dreamina / CapCut | No | `@Image1` tags; seed hidden; a "fixed camera" toggle that overrides the prompt; built-in avatar flows that sidestep the face block; different face rules (CapCut restricted real faces at launch [TCRUNCH 2026-03-26], while the 2.5 app guide promotes "realistic humans") [weaknesses report]. A shot that works there can fail with E005 on Replicate. |
| SYNTX | Unknown | Parameter mapping not researched (UNVERIFIED) |
| Gemini app | No | Wraps prompts with its own behaviour. Use **AI Studio** with `gemini-nano-banana-2.1` and an explicit `aspect_ratio` / `image_size` (UNVERIFIED detail). The Gemini API also exposes `person_generation` (`ALLOW_ALL`, `ALLOW_ADULT`, `ALLOW_NONE`) [GENAI]; Replicate exposes no such field. |
| ElevenLabs website | Partly | Free regenerations are website-only; the website and API discount credits differently [EL-PLAY]. Use the exact JSON body. |

**Generator requirement:** each shot emits a "lab card" containing:
1. The exact JSON for the shot's route (Replicate or Cloudflare).
2. Surface-rendered variants: Dreamina `@ImageN` text, plus a list of the settings the tester must set by hand.
3. The exact ElevenLabs JSON body.

---

## 2. Seedance prompt rules

### 2.1 Global rules (apply to every compiled prompt)

1. **Language.**
   - Write directions in English.
   - Write dialogue verbatim in Mexican Spanish, and **name the language before every line**. Otherwise the model may infer another language or accent [SD25PE l.829] **[FC]**.
   - Chinese prompts reportedly hit a cap around 1,800 characters [HIGGS].
2. **Length.**
   - Keep every prompt ≤2000 characters [CFDOC25][NICK][LV]. Replicate 2.0 allows 4000 [RS20].
   - Single-shot sweet spot: about 60–120 words. Reported ranges: 50–80 [HIGGS], 60–100 [ANIL], 50–150 [FALRM].
   - The **first 20–30 words carry the most weight** [ANIL].
   - Official 2.5 guidance sets no word limit; compress repeated style words first [SD25G].
   - "When a reference is accurate enough, do not describe the scene again" [SD25SPEC].
3. **Never put API parameters in the prompt:** aspect ratio, total duration, resolution, frame rate or the audio toggle [SD25PE][SD25G]. ComfyUI rejects `--param` tokens in prompts [COMFY].
4. **Describe positively.** Negatives are officially supported **only for subtitles and audio** on 2.5 ("No subtitles", "No BGM; generate only environmental sounds and action sounds", "No audio") [SD25G]. The official storyboard example also carries a `[Strictly exclude]` block for **styles** [SD25G mirror] **[FC]**. On 2.0: subtitles, logo and watermark [BDPE]. Never negate an action or emotion: "he's not crying" reads as "crying" [HEYUAN 2026-07-11].
5. **Write like a screenwriter describing a shot.** The filter reads intent; a bare subject prompt fails more often [HIGGS]. Use physical specifics, not keyword stacks such as "cinematic, 8K, photorealistic" [EMILY].
6. **Emotion goes into the body:** "jaw clenches, nostrils flare". The official 2.0 table maps anxiety to "fingers tapping, rapid breathing, evasive eyes" [SD20G][HIGGS]. **No idioms or metaphors**, because they render literally [SD25G][EMILY].
7. **Motion needs a degree adverb.** Moderate exaggeration helps [SD10G]. **Avoid the word "fast"**, which "tends to cause jitter"; describe the physics instead [FALRM].
8. **Show the trigger before the reaction.** Each stage gets one primary state change and an explicit **End state** [SD25PE].
9. **Never invent dialogue.** Keep the exact quoted words [SD25PE].
10. **Do not name directors, celebrities, brands or IP** [MAYST][MANJU].
11. **Avoid homographs** (tearing, shoot, draw, break, pound, snap) [HIGGS]. **[FC]** "Drone" and "FPV" are a *soft* lint only. One field report tied them to E005 [VSB], but the official 2.5 guide lists FPV and aerial as working techniques, and Cloudflare's official example "A dramatic drone shot…" completed [SD25G][CFDOC25]. Prefer "aerial flythrough".
12. **Each reference asset gets exactly one role.** Unassigned assets are listed as unused. **Never bind a character by writing their name inside the image** [SD25G][SD25PE].

### 2.2 Block order per mode

**A. Image-to-video, single shot (2.0 and 2.5). This is the default in our pipeline.**

```
1 FORMAT      Single continuous shot, no cuts.
2 CLEAN_HEAD  (night/low-light only) Clean low-noise image; dark areas stay clean without colour noise.
3 BEGIN       The clip begins exactly at this moment.          (when the start frame is mid-scene)
4 ACTION      <subject by role/wardrobe, never re-described> <one primary action + degree adverb>,
              <1–3 micro-motions>; End state: <visible end state>.
5 CAMERA      <one move: target, start, direction + speed, endpoint>
              | Static locked-off camera on a tripod; the frame does not move.
6 LIGHT/ENV   <named source, direction, falloff>; <environment motion>; <at most one light change>.
7 SOUND       <dialogue line, §2.6>; <named timed SFX>; <ambience>. No BGM.
8 LOCK        <identity/wardrobe/screen positions/camera side stay as in the image>.
9 FORMAT_NEG  No subtitles, no on-screen text.
```

Why this order:
- **Line 1.** 2.x cuts on its own unless told not to: "if you do not tell Seedance to avoid cuts, it may cut" [OPUS][EMILY].
- **Line 2.** The official fix for dark-scene noise puts the clean-image constraint **at the head** of the prompt [BDPE typical-effect-cases]. Lines 1 and 2 conflict over who goes first; both stay inside the first 30 words. Test the order (§8).
- **Lines 3–4.** I2V should "not redescribe static information already defined by the image" [SD25G]. Restating it gives the model two competing instructions for the same pixels, which causes drift [weaknesses report via EMILY]. Describe moving parts only, using the formula "subject+movement, background+movement, camera+movement" [SD10G].
- **Line 8.** A single preservation line, repeated in identical words in every block [EMILY][VENICE].

**[FC] On the Cloudflare `use_virtual_avatar` route, the start frame is only approximate** [VSB-S]. Add a short composition sentence (blocking, shot size, screen positions) even in I2V, because the image no longer pins it.

Two I2V variants [weaknesses report via HIGGS]:
- **Hold mode:** 3–4 micro-actions (blink, breath, hair drift) plus a double lock: "she stays seated; she does not stand, turn, or leave frame".
- **React mode:** one emotion split into sub-beats over 2–3 s.

**B. Seedance 2.5 production brief (multi-beat, reference mode, or long takes).** These are the official four blocks [SD25G][SD25PE]:

```
[Reference Material Roles]   (reference mode only; numbered by array order)
[Image1] defines <who/what>; use <x>, ignore <y>.  …  [Unused Materials] …
[Summary]   <Subject> + <Location> + <Event> + <Genre/Style> + <Camera family>.
[Timeline]  0-4 seconds: <visual, camera, action, dialogue, sound>. End state: …
            4-9 seconds: …
[Constants] <what stays constant: identity, light, environment, camera family, sound>. No BGM. No subtitles, no on-screen text.
```

The official basic template is:

> `<Subject> performs <primary action or event> in <scene and environment>. The visuals feature <visual style or emotion>. Use <shot size, camera angle, camera movement, or cuts>. Audio includes <dialogue, ambience, sound effects, or music>.` [SD25PE]

**C. Seedance 2.0 multi-shot.**
- Use `Shot 1:` / `Shot 2:` labels in event order. **No seconds.**
- Within each shot, write in this order: camera move or cut → subject action and expression → position/space change → audio [SD20G].
- One camera move per shot. Official examples use 3 shots per 15 s.
- Quality, style and constraints go at the end [SD20G].
- **Use Shot labels only for real cuts.** A single take with a push-in is prose plus "single continuous take".

**D. Text-to-video** (no identity lock). Use it for empty establishing shots, weather and extras.
- Formula: subject + appearance + action/event + scene and environment + visual style + camera/shot cuts + sound [SD25RES][SD20G].
- T2V is not face-filtered [REALAMAN].

**E. First + last frame** (`image` + `last_frame_image`, `aspect_ratio:"adaptive"`):

> "Preserve [X]. Generate a continuous transition from [A] to [B]. Motion: [one path]. Camera: [one move or locked]. Lighting: [source and continuity]. Sound: […]"

- Split hard transformations into A → midpoint → B [EMILY first-last-frame-guide].
- Both frames must share the aspect ratio [SD25G][ARKAPI].

**F. Start frame passed as a reference (reference mode).**
- Use the exact standalone sentence `[Image1] is the first frame.`, followed by a new sentence on composition and camera direction [SD25G].
- **The opening only approximates the frame, and the ratio is not locked** [SD25G][SD25SPEC].
- **[FC] Keyframe mode, for strict alignment:** pass each keyframe as its own image, in order, and open with "Use Images 1 to N in order as keyframes." [SD25G §5]. Storyboard grids (≤15 panels, line art, no text) are only a loose plot reference.

**G. [FC] 2.5 edit and extend (locked tasks).**
- **Editing:** `reference_videos` + `duration:-1` + `adaptive` + `mov` recommended, plus a trigger word: *edit video, add, insert, remove, delete, modify, replace, change to*.
- **Extension:** `adaptive`, user-set duration, plus a trigger: *extend forward, extend backward, continue, continue from, extend the story*.
- With several input videos, the prompt decides which one is edited.
- Edited output can differ by ≤0.3 s, or by 0 s if the source was made by 2.5 [SD25G §2][SD25SPEC].

### 2.3 Timing, density, multi-shot

- **2.0:** shot numbers only. Timestamps are ignored per the official guide [SD25G], although Replicate's blog demos `(7-12s) Hard cut to…` on 2.0 [RBLOG]. This is a conflict to test; until then, treat times as hints at most.
- **2.5 format:** integer seconds, `0-3 seconds:` or `[0s-3s]`. Point times ("at the 5-second mark") and relative times also work.
- **Windows must be contiguous, with no gaps.** The model invents whatever falls in a gap [SD25G].
- **Content per window.** Too little lets the model improvise; too much causes extra cuts or dropped beats. Never use timestamps for frequency ("3 times per second") [SD25G].
- **Transitions need a trigger and a method:** "At 5 seconds, the camera whip-pans rapidly to the left and completes the transition" [SD25G].
- **Shots per call:**
  - Official 30 s examples run 8–9 shots [SD25G].
  - Field guidance: ≤4–6 shots per 30 s [EMILY].
  - 2-shot generations are the most reliable. On transitions, Seedance 2.5 scored 0.466 with 2 shots and 0.416 with 5–6 shots. J/L-cut execution was 0.338. Transitions "degenerate into hard cuts" [CUTCRAFT 2026-09-15].
  - **Rule: ≤3 shots per call; do J/L cuts, dissolves and cut timing in the edit.**
- **Density formula** [EMILY multishot-grammar, 2026-09-26] (FIELD):
  - S = D ÷ (beats + L), where L sums: camera move 0.5; spoken line 1 per 8 English words; extra principal acting 1; precise contact 1; location change 2; synced sound cue 0.5.
  - S ≥ 3 is safe; 2–3 is a stretch; below 2 means split the generation.
- **Emotional beats** get at least 2 s [prompting report, FIELD].
- **Action-reversal fill:** if an action ends early, the model plays it back in reverse to fill the time. Chain 2–3 actions in the same direction and name the camera's end frame. Name completion states: "the door clicks fully shut" [HIGGS].
- **Characters across cuts:** track ≤3 characters. A character who exits frame is gone for the rest of that shot. Off-screen state changes don't exist. Re-anchor positions after each cut, and change both shot size and camera character at every cut [HIGGS].

### 2.4 Camera vocabulary

The official list works directly [SD25G]:
- **Shot sizes:** extreme wide, wide, medium, medium close-up, close-up.
- **Moves:** push in, pull out, pan, track, follow, orbit, dive, tilt up, handheld shake.
- **Angles:** low angle, overhead, first-person.
- **Named techniques:** one-take (long take), dolly (Hitchcock) zoom, aerial, FPV (official; soft lint, see §2.1 rule 11 **[FC]**), bullet time, speed ramp.

Every camera term needs a target subject, a start, a direction and speed, and an endpoint [SD25PE]. Prefer focal lengths ("35mm", "85mm") over camera brand names [MANJU-related auto-dramaflow, FIELD].

| Move | Status / rule |
|---|---|
| Static | Default for dialogue, lip-sync, faces and text. Replicate 2.x has no `camera_fixed` (no-op on Cloudflare), so write "Static locked-off camera on a tripod; the frame does not move." [CFDOC25][prompting report] |
| Push in / pull out | Reliable. Add speed ("very slow") and an end frame ("ending on her hands") [SD25G][HIGGS]. |
| Pan / tilt / follow / track | Reliable. When tracking, state that the camera matches the subject's speed [HIGGS]. |
| Orbit / arc | Works, but risks identity drift at profile angles [MINDST, UNVERIFIED 62% claim]. **Avoid on hero faces.** |
| Crane / dive / aerial | Works. Avoid during dialogue. |
| Handheld | State which subject is followed and how much shake [SD25G]. Heavy shake costs identity and lip-sync. |
| Whip pan | Only as a timed transition with a trigger [SD25G]. |
| Rack focus | Requires the explanation form: "Rack focus: the focus shifts smoothly; the foreground… becomes blurred, while the character in the background gradually becomes clear." [SD25G] Don't stack it with other moves. |
| Dolly zoom | State the subject size to preserve and whether the background appears to move closer or farther [SD25G]. |
| **Failure rules** | One primary move plus at most one texture modifier ("slow dolly in, slightly handheld"). Compound moves jitter. A move with no endpoint drifts or reverses. Walking glides unless you write "heel lands first, strict left-right alternation". [HIGGS][EMILY] |

### 2.5 Reference syntax per surface

| Surface | Image | Video | Audio | Source |
|---|---|---|---|---|
| **Replicate / Cloudflare 2.0 / 2.5** | `[Image1]` | `[Video1]` | `[Audio1]` | [RS25][RS20] |
| Dreamina / CapCut / Jimeng | `@Image1` (docs also `@Image 1`) | `@Video1` | `@Audio1` | [SD25G][LUKSURF] |
| fal | `@Image1` | | | [FALRM][MAJIK] |
| BytePlus API | `content[].role` = `first_frame` / `last_frame` / `reference_image` / `reference_video` / `reference_audio`, plus "Image 1" in the prose; `asset://<id>` | | | [SD25G][ARK74] |

The official docs also use `[Video 1]`, `<video1>`, `<2pic>` and `Images 1-2` [SD25SPEC].

Rules:
- **Numbering follows array or upload order,** not mention order [SD25G].
- **Earlier references weigh more,** so order by importance [FALRM][BDPE].
- **Never translate or renumber a tag** [SD25PE].
- **Binding examples:**
  - "[Image1] defines Lupe's face, hairstyle and grey rebozo. Do not use the image background."
  - "Images 1-2 are Character 1 and correspond to Audio 1." [SD25G]
- **If `<>` is used for SFX, do not also put names in angle brackets** [SD25PE].

### 2.6 Audio and dialogue syntax

| Content | Syntax in ByteDance material | Example |
|---|---|---|
| Music | `( )` | `(soft piano in the background)` |
| SFX | `< >` | `<a single floorboard creak behind her>` |
| Dialogue | `"…"` (official 2.5 worked example `Dialogue (<speaker>): "<line>"`; Replicate schema; ComfyUI tooltip) **or** `{ }` (sd25-pe formula, other guide rendering) **[FC]** | `"¿Quién anda ahí?"` / `{¿Quién anda ahí?}` |
| On-screen text | `【 】` | (we never use it) |

Sources: [SD25G][SD20G][RS25][COMFY].

**[FC] Renderer option `quote_style`:** default `double_quotes` on **both** 2.0 and 2.5; `braces` is the A/B arm in the test pack.

**Dialogue line formula (official):**

> `Dialogue language + regional variety/accent + delivery style + Speaker + "line"` [SD25PE]

- Label every line separately, with the language and accent **before** the line. Field reports say delivery drifts otherwise [PJACE]. sd25-pe also says not to make one blanket declaration at the start [SD25PE l.829].
- Write "Mexican Spanish (Mexico City accent)", never just "Spanish". 2.5 casts voices from what it infers in the image; a British accent appeared unprompted [MINDST].

**Speech control:**
- "speaks only this line, once; everyone else stays silent" [HIGGS].
- Other visible faces: "listen with their mouths naturally closed" [SD25PE].
- No-dialogue shots: "characters keep their mouths naturally closed, there is no narration, only the specified ambience remains" [SD25G].

**Line-length budgets** (FIELD, measured in English):
- 5–10 words per line, locked camera, no head turns [SAGNIK][EMILY].
- **Lines of ≤6 words in a 4 s shot came back wrapped in invented mumble; 8–12-word lines were clean (4 of 4)** [HIGGS FAILURE-MODES 2026-08-09].
- Mouths get "mushy" past about 8 s [SAGNIK].
- If English lines don't fit the duration, the model can switch to rapid Mandarin [BDPE typical-effect-cases]. Spanish is likely similar (UNVERIFIED).
- **Rule:** fit the duration to the line. Script any remaining time explicitly: "Then her lips close; only the drips are heard."

**Sound mix:**
- Name specific, timed sounds per shot; the model otherwise invents defaults from what it sees [SD25G].
- Describe the room tone. "Voices clean and close to the microphone, ambience dips when someone speaks" [HIGGS].
- "No music" sometimes loses. A dedicated line works better: `[SOUND] Strictly only naturally occurring sound and foley, no music allowed.` [PJACE]
- **Policy:** request "No BGM" per clip, score in post, and unify the per-clip audio in the mix [SD25G][OSOD].

**[FC] Reference audio semantics (official):** "When written dialogue conflicts with the content of reference audio, the user's text controls the words. By default, the audio supplies only voice characteristics, accent, speed, and emotion" [SD25PE l.227]. So `[Audio1]` conditions the voice; it does not play your file back.

### 2.7 Negatives: the whitelist

There is no `negative_prompt` parameter on any Seedance surface [RS25][RS20][CFDOC25][FALRM]. (Veo 3.1 and Kling v3 on Replicate do have one [GFV].) Only these phrases are allowed, and they go at the end of the prompt except FORMAT:

- `Single continuous shot, no cuts.` (start of the prompt)
- `No subtitles, no on-screen text.` (every shot; subtitles appear in 60–90% of outputs at baseline, more often in vertical video [BDPE troubleshooting V-2])
- `No BGM.` or `No BGM; only ambience and action sounds.` or `No audio.`
- `No logo, no watermark.`
- An anti-twin line ("only one woman appears") only for multi-person shots [BDPE]. Note that [SD25PE] says not to add blanket bans unless needed.
- **[FC]** A short `Strictly exclude: <styles>` line is legitimate, because the official storyboard example uses it [SD25G mirror]. Use it for styles only (e.g. "cartoon, CGI plastic look").

Everything else is phrased positively: "the doorway stays empty and black", not "no person in the doorway".

### 2.8 Example prompts

These were built from the rules above and **have not been run yet**. **[FC]** Dialogue is now in double quotes (default); `{}` is the A/B arm.

**E1. 2.5 I2V, no dialogue, face-free start frame (back to camera).** Replicate payload:

```json
{"prompt":"<E1>","image":"https://…/E01_S02_SH04_start.png","duration":6,"resolution":"480p",
 "aspect_ratio":"adaptive","generate_audio":true,"output_format":"mp4","seed":41721}
```

> Single continuous shot, no cuts. Clean low-noise image; dark areas stay clean without colour noise. The clip begins exactly at this moment. The woman with the flashlight takes three slow steps down the corridor, the beam trembling slightly in her hand and sweeping from the cracked floor tiles up to a half-open wooden door at the far end. End state: she stops two metres from the door. Camera: slow push in from behind her right shoulder at her walking pace, ending framed on the dark gap of the door. The flashlight beam is the only light source, steady intensity; outside the beam the corridor stays very dark but readable; dust drifts through the beam. Sound: her uneven breathing, shoes scraping grit on tile, <one wooden creak from behind the door at the very end>. No BGM. Her hair and clothing stay exactly as in the image; the corridor layout stays the same. No subtitles, no on-screen text.

**E2. 2.5 I2V dialogue shot, hybrid lip-sync arm A (§5.9).** Settings: `duration: ceil(ElevenLabs_line_s + 1)`, minimum 4; `generate_audio:true`.

**[FC] Route:** this needs a visible-face start frame, so it **cannot run on Replicate Seedance**. Run it either:
- on Cloudflare with `use_virtual_avatar:true` (start frame approximate; add composition text), or
- on `google/veo-3.1` / `kwaivgi/kling-v3-omni-video` with the same prose (re-validate the grammar), or
- on Replicate with a half-shadowed profile medium close-up that passes the face filter (test).

> Single continuous shot, no cuts. The clip begins exactly at this moment. Static locked-off camera on a tripod, medium close-up; the frame does not move. The woman lowers the flashlight slightly, eyes fixed past the camera on the dark doorway, her breath visible in the cold air. After one breath, in Mexican Spanish with a Mexico City accent, a slow trembling whisper, she says only this line, once: "¿Mamá? ¿Eres tú? Contéstame, por favor." Then her lips close and stay still; her jaw tightens; her eyes do not leave the doorway. Sound: close, dry whisper; slow water drips; a distant generator hum; after the line only the drips. No BGM. Her face, hair and clothing stay exactly as in the image. No subtitles, no on-screen text.

**E3. 2.5 two-beat scare in one take** (`duration:5`, I2V). Adapted from [directing report]:

> One continuous take, no cuts. Night, a narrow 1990s kitchen in a rural Mexican house; the woman from the first frame stands alone at the sink. Slow-burn realistic horror.
> [0s-3s] Locked medium shot at eye level. She rinses a clay cup under a thin stream of water, then stops; her shoulders rise as she holds her breath. The doorway on screen right behind her stays empty and black.
> [3s-5s] Very slow push-in toward her face. Her eyes, not her head, turn toward screen right. Deep in the doorway a pale, motionless figure stands out of focus.
> One bare bulb above the sink is the only light: warm hard light on her face and hands, deep but clean shadows, the background readable as dark blue-grey. She stays screen-left facing right; the camera stays on the sink side. Sound: water trickle, fridge hum, <a floorboard creaks off-screen at second 3>, then near-silence. No BGM. No subtitles, no on-screen text.

(**[FC]** If her face is visible in the start frame, this needs the face route; see E2.)

**E3 for 2.0.** Delete the `[Xs-Ys]` markers and keep the prose sequential: "…holds her breath. Then the camera very slowly pushes in…". Delete "at second 3" and write "near the end". No Shot labels, because there is no cut.

**E4. 2.5 reference mode with an ElevenLabs line.** **[FC]** On Replicate this is refused if the face reference is photoreal. Run it on Cloudflare with `use_virtual_avatar:true` (AI-made character only):

```json
{"prompt":"<E4>","reference_images":["…/sh09_layout.png","…/lupe_face_v1.png"],
 "reference_audios":["…/sh09_lupe_es.mp3"],"duration":5,"resolution":"720p",
 "aspect_ratio":"16:9","generate_audio":true,"use_virtual_avatar":true}
```

> [Image1] is the first frame. Lupe stands in a medium close-up in the dark kitchen, flashlight low, facing camera-left. [Image2] defines Lupe's face, hair and grey rebozo; do not use its background. [Audio1] is Lupe's voice; in Mexican Spanish she says exactly: "No te voy a dejar entrar." Static locked-off camera; her head stays still while she speaks, then her lips close. Low room tone under the voice; no other voices. No BGM. No subtitles, no on-screen text.

**[FC] Resolved: what the audio reference does.** Per sd25-pe, the text controls the words and the audio supplies voice characteristics, accent, speed and emotion [SD25PE]. The output voice is re-synthesized and is not your file [A1]. The final audio track stays the ElevenLabs file.

---

## 3. Seedance weaknesses and mitigations to encode

| # | Weakness | Mitigation (template rule or validator) | Sources |
|---|---|---|---|
| 1 | Photoreal faces in input images rejected (E005), AI-made ones included **[FC: confirmed 2026-10-07]** | Add a per-shot `face_visible` field (none/partial/clear). `clear` → mandatory face route (§6.2): Cloudflare avatar, ModelArk asset, Veo/Kling, or redesign. Default to face-light start frames: back, profile, silhouette, deep shadow, hands, POV, wide shots. | [COMFYPR][ZEKE][NICK][RECOUP][VSB-S] |
| 2 | Unprompted cuts | First line is "Single continuous shot, no cuts." Shot labels or timestamps only when cuts are intended. | [OPUS][EMILY] |
| 3 | Identity and wardrobe drift (faces mostly hold; costume, hairline and props drift: "failed 11 of 24 on costume alone") | I2V never re-describes appearance. One identical lock line per block. No orbit on hero faces. Face shots ≤8 s. A vision-model costume check in QC (§6.9). | [CSARKO][EMILY][MINDST] |
| 4 | Multi-subject bleed, "twin faces", frozen extras | Each person gets distinct hair and wardrobe, a screen position and a tag. One person acts; the others get persistent micro-motion. Track ≤3 characters. More than 4 people is unstable on 2.0, so build intermediate frames with ≤4. Two-person dialogue = one-speaker clips. Treat crowds as environment. On 2.5, >5 subjects → single-view refs [SD25G]. | [EMILY][BDPE][HIGGS] |
| 5 | Hands | Hands at medium distance. One simple grip. No finger work. No touching the face during dialogue. | [VIDEOAI][EMILY] |
| 6 | Text and signage ("glyph soup") | Clean frames everywhere. All text (REC overlays, signs, titles) added in post. | [VIDEOAI][BDPE] |
| 7 | Fast motion morphs; "fast" causes jitter | Ban the word "fast". Write force, timing and end state. Split complex action across cuts. | [FALRM][MINDST] |
| 8 | Compound or endless camera moves | Enum with one move per beat, plus at most one texture modifier. Endpoint required. | [HIGGS][EMILY] |
| 9 | Action reversal; truncated actions | Chain 2–3 actions in the same direction. Name the completion state. | [HIGGS] |
| 10 | "Nobody moves" freezes the frame | Held tension plus one micro-event every 1–2 s. | [prompting report via HIGGS] |
| 11 | Emotion words give a shallow look; idioms render literally | Map emotions to body physics through a lookup table (§6.7). | [SD20G][EMILY] |
| 12 | Walking glides | Use "heel lands first, strict left-right alternation". | [HIGGS] |
| 13 | Mirrors and reflections break geometry | The reflection gets its own shot as the primary subject, or composite it in post. | [VIDEOAI][HIGGS] |
| 14 | Hero water, fire, splashes | Keep fluids in the background (drips, rain on glass). Route hero fluids to Kling 3.0 or Veo 3.1 (faces accepted per [VSB-V]; horror policies UNVERIFIED). | [ATLASCMP][VSB-V] |
| 15 | Dark scenes come out "dirty", noisy, flickering | Start frames dim but readable with clean shadows. CLEAN_HEAD line. One steady named source and at most one light change per shot. Never prompt "grainy", "VHS" or "pitch black". Grade, crush and add grain once in post (denoise → upscale → grade). Avoid "glow", "glimmer", "glints". | [BDPE typical-effect-cases][WAVESPEED][CSARKO] |
| 16 | Unwanted subtitles (higher in 9:16) | Whitelist negative on every shot. 16:9 masters. OCR check in QC. | [BDPE][NICK][VSB-S] |
| 17 | Dialogue babble, extra words, language switching | Fit the line to the duration (§2.6). "Says only this line, once". Others' mouths closed. Name the language per line. Whisper ASR check in QC. | [HIGGS][BDPE][SD25PE] |
| 18 | Accent drift; voice changes between clips | Accent stated on every line. ElevenLabs is the voice of record; Seedance audio is only a guide (§5.9). | [MINDST][EL-V4] |
| 19 | Quality degrades past ~15 s; 30 s means more chances to fail | 5 s default; 5–8 s is the reliable band. Long takes only for slow atmosphere shots. | [EMILY][ANIL] |
| 20 | Extension seams; decay across chained extensions | At most 2 extensions, then re-anchor from canonical refs. Use `mov` and the extension trigger words (§2.2 G). Trim 6 frames from the end of the previous segment and 1 frame from the start of the next. | [BDPE][SD20G][VSB][SD25G] |
| 21 | Seeds not reproducible; resolution changes the result | Log everything, including the seed recovered from logs. Don't expect a 480p take to reproduce at 720p. | [ANIL][RIFF] |
| 22 | Prompts from 2.0 break on 2.5 | A separate compiler profile per version; re-validate the template set on any model switch. | [MINDST][SD25G] |
| 23 | Weak transitions, J/L cuts and editorial logic | Generate ≤3 shots per call. All transitions, J/L cuts and stings in the edit. | [CUTCRAFT] |
| 24 | 180-degree rule and eyelines across separate clips | Enforce blocking in the start frame (Nano Banana) plus a text lock line (§6.5). On the avatar route, also in prose. | [manju/storyboard repos][VENICE] |
| 25 | Output moderation on horror; some prompts accepted on 2.0 are rejected on 2.5 | Classify failures; rewrite per class (§6.10, §7). | [MINDST][THESOURCE] |
| 26 | Variable-frame-rate output; end-of-clip audio click; missing audio stream | `ffmpeg -r 24 -vsync cfr`; 0.5 s audio fade-out; ffprobe audio check **[FC]**. | [REALAMAN][BDPE][VSB-V] |
| 27 | Small or distant faces lose fidelity | Acceptable for extras. Hero identity only at MS or closer. | [prompting report] |

---

## 4. Image refs and start frames (Nano Banana)

### 4.1 API rules

- **Send only schema fields.** Nano Banana, NB2 and Pro on Replicate have **no `seed` and no `negative_prompt`** [L1][PUTER]. The 2.1 schema is UNVERIFIED **[FC]**.
- **`allow_fallback_model:false`** on Pro.
- **`google_search:false, image_search:false`** on 2.1 (if present) and NB2.
- **`output_format:"png"`** for refs and frames.
- **Always set an explicit `aspect_ratio`.**
- **Pixel sizes at 1K** [COOKBOOK] (re-verified **[FC]**):
  - 16:9 = **1344×768** (1.75, not 1.778)
  - 9:16 = 768×1344
  - 2:3 = 832×1248
  - 3:4 = 864×1184
  - 4:5 = 896×1152
  - 21:9 = 1536×672
  - 1:1 = 1024×1024
  - Exact 2K and 4K sizes are UNVERIFIED.
- **Normalize after generation:** centre-crop and resize every start frame deterministically to the video input size (1280×720 for 16:9 720p). Store both the raw and the normalized file.
- **Safety signals** [VERTEXRAI]:
  - `IMAGE_SAFETY`: output withheld; tunable.
  - `PROHIBITED_CONTENT` / `IMAGE_PROHIBITED_CONTENT`: non-configurable.
  - Log either one and route to a rewrite; do not retry blindly.

### 4.2 Prompt rules (Google official) [GCBP 2026-03-06][GDEVIMG][COOKBOOK]

1. **Write a narrative paragraph, not a keyword list.** Be hyper-specific about subject, composition, action, location and materials ("navy blue tweed").
2. **Use semantic negatives:** describe the desired state positively, e.g. "an empty, deserted street". Short descriptive "with no …" phrases are acceptable; bare keyword negations are not.
3. **Use camera and photo terms:** shot type, lens ("85mm"), aperture, angle, a named lighting setup, a film look.
4. **Photoreal template:**
   > "A photorealistic [shot type] of [subject], [action or expression], set in [environment]. The scene is illuminated by [lighting], creating a [mood] atmosphere. Captured with a [camera/lens], emphasizing [textures]."
   - With references: `[Reference images] + [Relationship instruction] + [New scenario]`.
5. **Assign roles by ordinal:** "Take the garment from the second image and place it on the person in the first image" [GRECIPE].
6. **In edits, state what stays the same:** "Keep everything the same, but change…".
7. **Fixed rules go in a system-level preamble:** "a simple image, no panels; a full image with no borders, titles, nor description" [COOKBOOK Book_illustration]. On Replicate there is no system field, so prepend a constant block.
8. **Character DNA:** an LLM writes a character prompt of ≥50 words, which is reused **verbatim** in every scene prompt [COOKBOOK].
9. **Avoiding the "AI look":**
   - Official levers: a named film stock or lens, a named lighting setup, materials [GCBP].
   - Practitioner levers (UNVERIFIED): "natural unretouched skin with visible pores, fine vellus hair, slight unevenness"; avoid "flawless, perfect, stunning, 8k, masterpiece".
   - "Photorealistic" is fine **in Nano Banana prompts**. Keep it out of Seedance prompts (§7).
10. **Start-frame prompts describe a static composition only:** blocking, lens, light, wardrobe, props, exposure. No motion verbs [OSOD].

### 4.3 Character kit strategy

1. **Base portrait (identity anchor).**
   - Text-only call: front-facing head and shoulders, plain light-grey seamless backdrop, soft even light, 2K PNG.
   - Model: Pro or 2.1; A/B both.
   - Generate several, pick one, store it as `approved`. **The image is the identity, not the prompt.**
   - **[FC]** This portrait is also the right input for the Cloudflare avatar route (face reference plus a separate full-body wardrobe reference) [VSB-S].
2. **Derived views, one call each, with the base attached as Image 1:** three-quarter, profile, full body (2:3), then 3–5 expressions.
   - Each prompt restates the full DNA and adds "Only the camera angle changes; identity, hair and clothing stay identical. A single full-bleed photograph." This is Google's 360-view method [GDEVIMG].
3. **Variants** (wet, injured-lite, 1994 version) are derived from the base plus the closest view, **never from another variant**.
4. **One image per view, never multi-panel sheets for production.**
   - The cookbook forces "no panels" [COOKBOOK].
   - **[FC]** Seedance 2.5 officially supports multi-view subject images for 1–5 subjects; split views only for >5 subjects [SD25G]. One view per image is our convention for consistency and caps, not an official 2.5 ban.
   - Seedance 2.0 discourages multi-view refs because they cause twins and ID drift. Use a face-only headshot plus a separate full-body wardrobe image, bound as "<Subject1>'s facial features refer to Image 1 (headshot), styling refers to Image 2 (full body)" [SD20G][BDPE].
   - Exception: collages only to pack more identity under a reference cap [COOKBOOK].
5. **Freeze and version the kit** (`LUPITA_face_v1`). "The moment you improve the hero shot in week two, every earlier shot becomes inconsistent" [CSARKO].
6. **In Seedance reference mode** (Cloudflare avatar or ModelArk asset route), use ≤3 stills per character in the same lighting [weaknesses report via medium/social], most important first.

### 4.4 Location plates

- One empty establishing plate per location and lighting state, 16:9, 2K.
- **No people in plates**, because the model may copy them. Write the emptiness positively: "an empty tunnel, deserted, only rock, timber and rails" [image report].
- Keep a per-location lighting bible: source, direction, colour temperature, contrast, time of day. Paste the colour and tonality text **verbatim** into every shot prompt, not a colour-chart image [directing report via color-script].

### 4.5 Start-frame composition

1. **Reference order:** **Image 1 = location plate; Images 2..n = characters in left-to-right screen order; last = key prop.**
   - Name each in the prompt: "Image 2 is Mateo, Image 3 is Vale".
   - Emit `image_input` in exactly that order.
   - Whether order matters to Gemini is UNVERIFIED; the convention makes it irrelevant.
2. **Attach only the people visible in the shot.** One reference per person: the view closest to the shot angle. Respect the caps: 2.1 ≤4 characters (UNVERIFIED); Pro ≤14 total / 6 high-fidelity [COOKBOOK].
3. **Decouple identity from everything else:** "take only their face, hair, build and clothing from Images 2–3; their pose, position, lighting and surroundings come from this scene description and from Image 1."
4. **Render at the exact delivery ratio.**
   - 2.5 I2V output follows the image ratio, so crop nothing afterwards [RS25][RIFF].
   - Keep a "protect 9:16" safe zone, with eyes and key action in the centre third.
5. **Compose the first instant of the motion,** with no mid-action blur.
   - "First frame quality determines ~70% of the video's baseline clarity" [BDPE].
   - Denoise before upload [WAVESPEED].
6. **Exposure:** dim but readable. The subject's face is caught by a motivated key, and shadows hold detail [BDPE][directing report].
7. **Blocking:** the start frame enforces the floor plan and the 180-degree line.
   - Make reverse angles as an **edit of the forward frame** ("same room, reverse angle, Lupita now screen-right facing left"), not as a new text-to-image call.
   - For a new angle in the same scene: canonical character refs plus the previous clip's tail frame as a **layout reference**. Never chain raw tail frames across angle changes [directing report].
8. **Face strategy [FC]:** on the Replicate route, design start frames as profile, three-quarter-away, back, silhouette, partial shadow or wide; this is mandatory, not just a stopgap. Describe the face in the Nano Banana prompt; the Seedance prompt carries only the lock line. Face-forward frames go to the face route (§6.2).
9. **Reveals and match cuts:** design them as still pairs, using `image` plus `last_frame_image` (e.g. empty doorway → figure in doorway) [directing report][CUTCRAFT].

### 4.6 Templates

All untested. Characters are adults; see §7.

**Base portrait:**
> A photorealistic head-and-shoulders portrait of Vale Ríos, a 19-year-old adult Mexican woman, facing the camera with a guarded, tired expression. She has black straight hair pulled into a high messy ponytail with loose strands, warm olive-brown skin, thick straight dark eyebrows and a small thin scar above her left eyebrow. She wears an oversized black denim jacket with frayed sleeves over a plain grey T-shirt. Plain light-grey seamless studio backdrop, soft even key light from camera left with gentle fill so every facial feature is clearly readable. Shot on an 85mm lens at f/4, natural unretouched skin with visible pores and fine baby hairs, true-to-life colour. A single full-bleed photograph of one person.

**Derived view (Image 1 = approved base):**
> Image 1 is the approved identity reference for Vale Ríos. Create a new photograph of the exact same woman — same face shape, eyes, nose, lips, eyebrows, the small scar above her left eyebrow, skin tone, ponytail and black denim jacket — now in a three-quarter view turned toward camera left, head and shoulders. Same plain light-grey seamless backdrop and the same soft even lighting as Image 1. Only the camera angle changes; her identity, hair and clothing stay identical. A single full-bleed photograph.

**Start frame:**
> Create one cinematic film still. Image 1 is the location: the abandoned silver-mine tunnel — keep its wet rock walls, timber supports and rusted rails exactly. Image 2 is Mateo Ruiz and Image 3 is Vale Ríos, both adults; use them only for each person's face, hair, build and clothing. Scene: Mateo stands on the left third, half-turned toward Vale, holding a flashlight low; Vale is on the right third, her back against the rock, looking past him into the dark. Lighting: darkness except the flashlight beam cutting through floating dust, warm falloff on their faces, deep teal shadows that still hold detail. Camera: medium two-shot at eye level, 35mm lens, shallow depth of field. Photorealistic 35mm film still with natural skin texture, muted desaturated palette. A clean frame of the scene only, with unmarked walls.

Payload: `{"prompt":…, "image_input":[plate, mateo_3q, vale_front], "aspect_ratio":"16:9", "resolution":"2K", "output_format":"png", "google_search":false, "image_search":false}` (2.1 fields UNVERIFIED; validate against the live schema).

**[FC]** This frame shows two faces, so on Replicate Seedance it will be refused. Either re-block it (both half-turned into shadow), or send the video step to the face route.

### 4.7 What not to do

- Do not send `seed` or a "Negative" block to Nano Banana on Replicate (§Appendix A).
- Do not use `google/nano-banana` or `google/nano-banana-2`.
- Do not use multi-panel sheets as production refs.
- Do not attach people who are not in the shot.
- Do not chain a variant from another variant.
- Do not write people into location plates.
- Do not put text, signs or dates in frames; add them in post.
- Do not render pitch-black or noisy frames.
- Do not use real-person photos [GPOL]. Never set `use_virtual_avatar` for a real person [VSB-S][CFDOC25].
- Do not leave `match_input_image` unset on text-only calls.
- Do not enable fallback or grounding.

---

## 5. Voice (ElevenLabs) and lip-sync

### 5.1 Model choice

1. **`eleven_v4` is primary.**
   - "A net upgrade over Eleven v3… in almost every case." Supports audio tags; lists "Spanish, LatAm (spa)" [EL-V4][EL-MODELS].
   - **Accent behaviour [FC]:** the voice keeps its native accent when its source language matches the output. When the languages differ, v4 deliberately "aims for fluent, natural-sounding speech in the target language rather than carrying over the reference accent" [EL-V4CAP]. **Use voices whose source audio is native Mexican Spanish.** A designed or English-source voice will not reliably sound chilango.
   - Risks:
     - Voice Design voices "may not be as performative or sound as good" on v4 [EL-V4][EL-VD].
     - Behaviour may drift over time, so cache and pin generated audio.
     - A tag can be read as a request for a sound effect; write voice-quality tags such as `[low, gravelly voice]` [EL-BP].
2. **`eleven_v3` as A/B fallback**, especially for designed voices. Same tags; discrete stability; 5,000-character limit; **no request stitching** [EL-BP][S21][EL-STITCH] **[FC]**.
3. **`eleven_multilingual_v2` as the safe fallback.** No tags; emotion comes from text and punctuation only [EL-API].

### 5.2 Exact body per model (code-ready)

| Model | `voice_settings` sent | `language_code` | Tags in `text` | Other |
|---|---|---|---|---|
| `eleven_v4` | `{stability, similarity_boost}` **only** | `"es"` | yes | `seed`; no SSML; stitching via `previous_request_ids` (≤3) **[FC]** |
| `eleven_v3` | stability ∈ {0.0, 0.5, 1.0} (snap), similarity_boost, style | `"es"` | yes | speed support reported both ways (UNVERIFIED); **no stitching** |
| `eleven_multilingual_v2` | stability, similarity_boost, **style 0** default, speed, use_speaker_boost | **omit** | **no** (likely read aloud; UNVERIFIED) | `previous_text` / `next_text` or `previous_request_ids` |

Always send `seed` and include it in the cache key. Request `output_format=mp3_44100_192` on the Creator plan [EL-API].

### 5.3 Tags (v4 / v3) [EL-BP][EL-V4]

**Placement and form:**
- Square brackets, immediately before or after the segment they modify.
- Ellipses add pauses; CAPS add emphasis.
- No SSML `<break>` (v3 and v4 do not support it [EL-BP]). Tags can be stacked: `[whispers] [nervously]`.
- v4 reads IPA between slashes, e.g. `/ˈtlalok/`, for names [EL-BP] **[FC]**.

**Content:**
- **Voice-describing tags only.** The official Enhance prompt bans non-voice tags: "DO NOT use tags such as [standing], [grinning], [pacing], [music]".
- **Never use SFX tags in dialogue files:** `[gunshot]`, `[explosion]`, `[applause]` and similar. v4 is trained on both delivery and SFX, so ambiguous tags can become sounds [EL-BP].
- Documented voice tags include: `[whispers]`/`[whispering]`, `[shouting]`, `[sighs]`, `[exhales]`, `[crying]`, `[laughs]`, `[curious]`, `[sarcastic]`, `[excited]`, `[surprised]`, `[thoughtful]`, `[short pause]`, `[long pause]`, `[exhales sharply]`, `[inhales deeply]`, `[clears throat]`, `[under his breath]`, `[Quietly, with controlled fear]`, `[Building tension, measured pace]`, `[Brief pause]`.
- Proposed horror tags (**untested**): `[terrified whisper]`, `[voice trembling with fear]`, `[panicked, breathless]`, `[screaming in terror]`, `[sobbing, voice breaking]`, `[hoarse, barely audible]`, `[flat, emotionless voice]`.
- **Tags in English, line in Mexican Spanish:** `[quietly, with controlled fear] ¿Oyeron eso? … [whispering] No toquen nada.` Whether Spanish-language tags work is UNVERIFIED.
- 1–2 tags per sentence. Match tags to the voice: "A meditative voice shouldn't shout" [EL-BP].

### 5.4 Settings per delivery

These are synthesized starting points, not vendor values. Validate them in the lab. Ranges and defaults come from [EL-API][EL-PLAY]; v3 snapping from [S21].

| Delivery | `eleven_v4` | `eleven_v3` | `eleven_multilingual_v2` (no tags) |
|---|---|---|---|
| normal | stab 0.5, sim 0.75, no tag or a mood tag | 0.5 / 0.75 / style 0 | 0.5 / 0.75 / **style 0** / boost true / speed 1.0 |
| quiet fear | 0.4 / 0.75, `[quietly, with controlled fear]` | 0.0 or 0.5, same tag | 0.4 / style 0 / speed 0.95; ellipses in the text |
| whisper | 0.4 / 0.7, `[whispering]` | 0.0, `[whispers]` | 0.35 / style 0 / boost false |
| shout | 0.3 / 0.8, `[shouting]` + CAPS on the key word + "¡…!" | 0.0, `[shouting]` | 0.3 / **style ≤0.3** |
| scream | 0.25 / 0.8, `[screaming in terror]` | 0.0 | 0.2 / style ≤0.4; expect retakes |
| crying | 0.3, `[sobbing, voice breaking]` | 0.0, `[crying]` | 0.3; write the break into the text: "No… no puede ser…" |

Official presets for reference: character voices stability 0.3 / similarity 0.8 [EL-SKILL]. "Most common setting is… keeping style at 0" [EL-PLAY]. The repo currently uses style 0.25–0.9 (Appendix A).

### 5.5 Short lines: generate the scene, not the line

- Very short inputs are v3's weak spot. One practitioner reports under ~250 characters as inconsistent, with tags sometimes read aloud [S22] (UNVERIFIED for v4). Our lines are 8–70 characters.
- **Default:** generate the whole scene with **Text-to-Dialogue `/with-timestamps`** (`model_id:"eleven_v4"`, ≤2,000 characters, ≤10 voices). Cut each line using `voice_segments`. Those timings set shot durations and lip-sync inputs [EL-TTD].
- **Fallback:** per-line TTS with `previous_request_ids` (v4) or `previous_text` / `next_text`. Generate 2–3 seeds per line and pick in the lab.

### 5.6 Spanish text

- **Language and region:** send `language_code:"es"` to v3, v4 and Flash only. The region (Mexico vs other LatAm or Spain) comes from the **voice** [EL-API][EL-V4][EL-V4CAP].
- **Numbers:** write them in Spanish words ("noventa y cuatro"); keep `apply_text_normalization:"auto"` [EL-BP].
- **Pronunciation:**
  - v4 accepts inline IPA between slashes.
  - Pronunciation dictionaries can be attached via locators, up to 3. Use them for Nahuatl place names and invented names [EL-BP][EL-API].

### 5.7 Voice Design

**Flow:**
1. `POST /v1/text-to-voice/design` returns `previews[]` with `generated_voice_id`.
2. `POST /v1/text-to-voice` saves one: `voice_name`, `voice_description`, `generated_voice_id` [EL-VD].

| Field | Value |
|---|---|
| `voice_description` | 20–1,000 characters (client-enforced [S23]) |
| `model_id` | **`eleven_ttv_v3`** (or `eleven_multilingual_ttv_v2`, the default) |
| `text` | preview text, 100–1,000 characters, in the character's own register; or `auto_generate_text:true` |
| `guidance_scale` | default 5; use 3–5 with longer prompts |
| `loudness` | −1..1 (0.5 default; 0 ≈ −24 LUFS) |
| `seed` | fixed ("Same seed with same inputs produces same voice") |
| `should_enhance` | false |
| `quality` | optional; higher = better, less variety **[FC]** |
| `reference_audio_base64`, `prompt_strength` | ttv_v3 only |

Official format [EL-VD]:

> `Native <Language>. <Gender>, <Age range>. <Quality>. Persona: <2–5 words>. Emotion: <2–3 adjectives>. <1–2 sentences on timbre, pacing, delivery>`

Our template, with ages kept adult (**[FC]** Voice Design reportedly refuses voices that read as a child [VSB-V]):

> Native Spanish, español mexicano del centro (Ciudad de México), sin rasgos de español peninsular. Male, early 20s. Perfect quality. Persona: recién egresado bromista. Emotion: playful, nervous, quick. Bright, slightly raspy young adult voice, fast conversational pace, close-mic, no background noise or reverb.

Run two lab arms:
- **(A)** Design with `ttv_v3`, then generate TTS with v3 and with v4.
- **(B)** Pick a native Mexican voice from the Voice Library (`GET /v1/shared-voices` with `language`, `accent`, `locale`, `gender`, `age`, `use_cases`, `search`, `page_size ≤100`) and use it with v4 [EL-SHARED]. The exact accent and locale strings are UNVERIFIED. Given v4's accent behaviour (§5.1), arm B is the more likely winner on v4.

### 5.8 Output and cost

- **Plan:** Creator is $22/month for 121,000 credits; credits roll over for up to 2 months [S20][EL-BILL]. "Text-to-speech costs one credit per character" [EL-INTRO].
- **Measured cost:** read the `character-cost` header on every call into the ledger [S24]. Per-1K-character API prices conflict (§1.8).
- **Format:** Creator **cannot** get `wav_44100` (Pro only). Generate `mp3_44100_192` and convert to WAV with ffmpeg for Sync and Seedance inputs [EL-API].
- **Scale:** voice cost is negligible. Part 1 has 538 dialogue characters, about 0.45% of monthly credits per pass [voice report].

### 5.9 Lip-sync: choice and arms

**Shot duration** for dialogue = ElevenLabs line duration (from timestamps) + 0.5–1 s, rounded up to whole seconds, with a minimum of 4 [voice report].

**[FC] Preconditions:**
- Lipsync only re-times a mouth that already moves; a still or closed mouth gets no lip movement [VSB-V].
- `sync_mode` only resolves a length mismatch [L1]. **Pad the ElevenLabs WAV with silence to the exact clip length**, then use `sync_mode:"cut_off"` (A/B `silence`).
- Every on-camera dialogue shot needs a face route (§6.2), because the speaker's face is visible.

| Arm | Video step | Lip-sync step | Final audio | Use |
|---|---|---|---|---|
| **A (default for on-camera lines)** | I2V with the **exact line** in the prompt (E2), `generate_audio:true`, so the mouth already moves with the right phonemes and timing. **[FC]** Run on the face route: Cloudflare avatar Seedance, or Veo 3.1 / Kling v3 Omni. | `sync/lipsync-2-pro`: video + padded ElevenLabs WAV, `temperature:0.5`, `sync_mode:"cut_off"` (A/B `silence`), `active_speaker:true` when more than one face is visible | ElevenLabs | visible dialogue |
| B | I2V where the character **visibly speaks** (prompt: "she talks, her mouth moves"), no specific line | lipsync-2-pro | ElevenLabs | if A drifts |
| C | Reference mode with `[Audio1]` = ElevenLabs line (E4). The audio conditions voice, accent, speed and emotion; the text sets the words [SD25PE]. | none, or lipsync-2-pro | Seedance audio if close enough, else ElevenLabs | Cloudflare avatar or ModelArk route only (Replicate refuses the face ref) |
| D | Silent take: line off-screen, back to camera, dark, or mouth hidden | none (lipsync cannot animate it) | ElevenLabs overlay | off-screen lines; cheapest; Replicate-safe |
| **E [FC: new]** | `prunaai/p-video` with `image` + `audio` = ElevenLabs line; the clip length follows the audio | none | ElevenLabs | cheap talking shots; Spanish mouth quality UNVERIFIED [VSB-V][GFV] |

Basis for the default:
- The weaknesses report recommends a silent plate (`generate_audio:false`) plus lip-sync in post. **[FC]** A silent, non-speaking plate gets no lip movement from Sync, so that plate must show speech motion (arm B).
- The voice report recommends arm A.
- **All arms are test arms.**

**Score each arm on:**
- bilabial closure on p/b/m ("**m**írenme", "**p**or a**qu**í");
- teeth flicker;
- identity drift;
- naturalness of the Spanish.

**Cost:** about $0.083/s on visible lines only (about $3.8 for part 1, $5.4 for part 2 per pass) [L2][voice report].

---

## 6. Directing rules for the generator (code and data)

### 6.1 Shot spec: the single source of truth

Prompts are compiled from the spec and never hand-edited. This follows [CINECREW]'s three layers (Narrative / Staging / Render). Removing the typed layer caused the largest drop in narrative coherence [CINECREW 2026-09-07].

```yaml
id: E01_S03_SH07
scene: E01_S03                 # scene holds floor_plan, axis, camera_side, lighting_bible
beat: {function: scare, story_turn: "Lupita realises she is not alone"}
  # enum: establish|investigate|dread_hold|reaction|insert|scare|dialogue|transition
duration: {edit_target_s: 2.5, gen_s: 5, use_window_s: [1.0, 3.5]}
route:
  provider: replicate          # replicate|cloudflare|modelark   [FC]
  model: seedance-2.5          # seedance-2.0|seedance-2.0-fast|seedance-2.5|veo-3.1|kling-v3-omni|p-video|other
  mode: i2v_first              # t2v|i2v_first|first_last|reference|keyframes|extend|edit
  resolution: 480p             # draft; final 720p
  aspect: adaptive
  seed: 1234
  generate_audio: true
  output_format: mp4
  quote_style: double_quotes   # double_quotes|braces (renderer option, §2.6)  [FC: default changed]
  virtual_avatar: false        # cloudflare only; true only for AI-made, rights-cleared people  [FC]
face_visible: partial          # none|partial|clear  -> routing (§6.2)
people:
  - {id: LUPITA, kit: LUPITA_v1, wardrobe: W1, screen: left, facing: right,
     eyeline: doorway, action: "rinses clay cup, stops", micro: ["shoulders rise"], speaking: false}
camera: {size: MS, end_size: MCU, angle: eye_level, lens_mm: 35,
         move: push_in, speed: very_slow, endpoint: "her face", shake: none}
  # move enum: static|push_in|pull_out|pan_l|pan_r|tilt_up|tilt_down|follow|track_l|track_r|
  #            orbit|crane_up|crane_down|handheld|whip_pan(transition only)|rack_focus|dolly_zoom
light: {source: "bare bulb above sink", direction: top, quality: "warm hard",
        exposure: dim_readable, change: null}
sound: {ambience: ["fridge hum", "water trickle"],
        sfx: [{t: 3, cue: "a floorboard creaks off-screen"}], music: none}
dialogue: null   # {speaker, lang: es-MX, accent: "Mexico City", delivery: trembling_whisper,
                 #  text, el_audio, el_audio_s, on_screen: true, lipsync_arm: A}
refs: []         # reference mode only: [{slot: Image1, asset, role, use, ignore}]
continuity:
  state_in: "cup full, tap running"
  state_out: "cup in right hand, tap running, figure in doorway"
  required_props: ["clay cup in right hand"]
  forbidden: ["extra people", "subtitles", "logo"]
handoff: {in: keyframe_new, out: none}   # in: keyframe_new|tail_frame|extend ; out: none|last_frame:<still>
qc: {identity_gate: per_character, checklist: auto, max_takes: 4}
```

### 6.2 Routing and validation rules

1. `mode ∈ {i2v_first, first_last, extend, edit}` → `aspect = adaptive` [RS25].
2. `refs` non-empty → no `image` or `last_frame_image`. `reference_audios` → at least one reference image or video on Replicate [RS25].
3. **[FC] `face_visible == clear` (or `partial` with a frontal or near-frontal face) → never `provider: replicate` + Seedance.** Choose `face_route`:
   - `cloudflare_virtual_avatar`: Seedance 2.5 on Cloudflare with `use_virtual_avatar:true`; field pass 2026-10-07 [VSB-S]. The start frame is approximate, so add blocking prose. AI-made, rights-cleared people only.
   - `modelark_asset`: `asset://` via the virtual library [COMFY][BPASSET].
   - `other_model`: `google/veo-3.1` or `kwaivgi/kling-v3-omni-video` on Replicate (faces accepted in field runs [VSB-V]). This needs its own prompt profile.
   - `redesign`: profile in shadow, back, wide, hands.
   - `smoke_test_passed`: only if §8 P0 shows a specific framing passes on Replicate.

   Record every E005 as a moderation result, not a bug [seedance-api report].
4. `dialogue.on_screen` →
   - `camera.move = static`;
   - one speaker;
   - `gen_s = ceil(el_audio_s + 1)`, clamped to 4..8 (mouth "mushy" past ~8 s [SAGNIK]);
   - line fits the duration, or the remaining time is scripted (§2.6);
   - face route required (rule 3).
5. `gen_s` limits: minimum 4. Maximum 15 (2.0; 12 with the Cloudflare avatar flag [VSB-S]) or 30 (2.5). Default 5. `dread_hold` ≤12. Never -1 except edit or extend.
6. Model 2.0 → Shot labels, no seconds. 2.5 → integer timestamps, contiguous from 0 to `gen_s`. At most 3 shots per call.
7. More than 3 tracked people → split the shot, or treat extras as environment. More than 4 on 2.0 → intermediate frames with ≤4 people [BDPE].
8. Prompt ≤2000 characters, with no parameter text (duration, ratio, resolution, fps).
9. Exactly one camera move per beat, plus at most one texture modifier.
10. Run the lint lists in §6.11.
11. **[FC]** Cloudflare payloads: only catalog fields; `fps:24`, `camera_fixed:false` and `watermark:false` may be sent; unknown keys fail.

### 6.3 Coverage per beat type

Synthesis of [directing report][EMILY][CSARKO][CUTCRAFT].

| Beat | Coverage | Edited length | Generation |
|---|---|---|---|
| Establish / re-anchor | wide, static or slow push | 3–6 s | 5–6 s; doubles as the lighting reference |
| Investigate | medium follow or locked medium | 3–5 s | 5–8 s, one move |
| Dread hold | locked or very slow push, negative space | 6–11 s | 8–12 s single take |
| Reaction | close-up | 1.5–3 s | 2.5: 2 shots in one 4–6 s call; the edit picks (face route if frontal) |
| Insert | extreme close-up | 1–2 s | 4 s minimum; bundle 2 inserts: "[0s-2s]…[2s-4s]…" |
| Scare | 0.2–1 s event + 2–3 s aftermath | 0.5–3 s | event at a fixed second, about 1.5 s clean handle on each side; cut to 6–20 frames in the edit |
| Dialogue | CU/MCU of the speaker, then the listener's reaction | line + 0.5 s | one line per clip; face route |

Series pacing (FIELD [EMILY]): hook by 3 s, a turn about every 15 s, a reaction beat after every line. Bundling 2 angles of the same moment into one 2.5 call gives coverage that matches, because the shots share a latent [CSARKO].

### 6.4 Prompt compilers

1. **Nano Banana start frame:** static composition only (§4.5–4.6).
2. **Seedance 2.0 profile:** §2.2 A or C.
3. **Seedance 2.5 profile:** §2.2 A, B, F (keyframes) or G (edit/extend).
4. **[FC] Veo 3.1 / Kling v3 profiles** for the face route: separate templates, to be researched. Both have `negative_prompt`.
5. **VLM QC checklist:** §6.9.
6. **Lab card:** §1.9.

Optionally compare 2.5 outputs against ByteDance's official `sd25-pe` skill:

```
npx --yes skills@latest add "https://arkdocs-en.tos-ap-southeast-1.volces.com/skills/" --skill sd25-pe --yes
```

[SD25PE]

### 6.5 Blocking and the 180-degree rule

- **Each scene has a floor plan:** named anchors (door, sink, window), an axis (A–B line), and a `camera_side`.
- **Each shot stores** `screen`, `facing`, `eyeline` and `camera_side`.
- **The compiler appends one lock line** to every Seedance and Nano Banana prompt: "Lupita stays screen-left facing right toward the doorway; the camera stays on the sink side." Placement "is re-inferred on every generation unless the prompt states it" [VENICE][MANJU][EMILY]. This matters even more on the avatar route, where the start frame is approximate **[FC]**.
- **Crossing the axis** requires a neutral shot or a continuous camera move that re-establishes geometry [directing report via script-to-shot-engine].
- **Seedance is weak at the 180-degree rule and eyelines across clips** [EMILY citing arXiv 2608.16717, UNVERIFIED]. Enforce them in the start frames.

### 6.6 Continuity handoff

| Cut type | Next start frame |
|---|---|
| Same-angle continuation | Last sharp frame of clip N (highest Laplacian variance in the final ~0.5 s), lightly restored. Or 2.5 extend (`duration:-1`, `mov`, trigger "continue from"). |
| Cut on action to a new angle | New Nano Banana frame: canonical refs + tail frame as layout reference + text for the new angle. **Never the raw tail frame.** |
| New scene or time jump | Fresh keyframe from canonical refs (re-anchor). |
| Match cut | Designed still pair: `last_frame_image` of N = A; `image` of N+1 = B. |
| Reveal | First + last frame: empty → occupied. |

Further rules:
- `state_out` of shot N becomes `state_in` of N+1, written in prose, and taken from **what the clip actually shows at its end**, not from the plan [EMILY].
- At most 2 extensions, then re-anchor [BDPE][EMILY].
- Splice trim: 6 frames off the end of the previous segment, 1 frame off the start of the next [SD20G].
- A face-bearing tail frame is also face-filtered on Replicate [RECOUP].

### 6.7 Horror craft rules (data)

- **Absence over reveal.** Declare negative space empty, then fill it. Keep the antagonist out of focus or in silhouette until the final second ("the autofocus refuses to lock on her") [OPENMONT].
- **Genre intention:** "make the audience afraid of what they cannot see". A very slow creeping push on a doorway that keeps the danger unseen; one bare practical; held silence with one off-screen cue [EMILY genre library].
- **One visible change per shot.** Lock the face in shot 1. Land the scare on **someone else's reaction**. Restraint over gore (a single drop in extreme close-up). Leave endings unresolved [GOODCASE via TAPC].
- **Silence before the scare:** room tone plus one named sound. Dead air invites babble or music [prompting report].
- **Light:** name the physical source, its direction and falloff. The flashlight beam is the only light, plus weak ambient fill. Dust or haze makes the beam visible [SD25G][EMILY lighting].
- **Found footage:**
  - Write the camera paragraph as a defect list: "strong handheld shake, imperfect framing, autofocus hunting, exposure shifts…", plus "No stabilization, no gimbal, no cinematic lighting".
  - **Never "4K, cinematic, sharp".**
  - REC and timestamp overlays go in post.
  - End with "The recording abruptly cuts to black" [TAPC].
- **Emotion → physical lookup** (seed list): fear = "breath catches, shoulders rise, steps back half a pace"; dread = "eyes, not head, turn toward the sound"; panic = "breath shallow and quick, hands shaking around the flashlight" [SD20G][EMILY].

### 6.8 Sound policy

- Seedance generates ambience and foley only ("No BGM").
- Music, stings, J/L cuts and transitions are done in post.
- BGM comes from a functional library ("suspense", "dialogue bed") with LUFS calibration and dialogue ducking [OSOD][CUTCRAFT].
- ElevenLabs is the voice of record.

### 6.9 QC gates (per take; budget 3–4 takes per kept shot)

| Gate | Method | Threshold / evidence |
|---|---|---|
| Start frame (before paying for video) | VLM check: blur, warped edges, blocking vs floor plan, wardrobe, extra people, text, hands, **face visibility vs route** **[FC]** | "One Sentence One Drama" frame reviewer [OSOD] |
| Identity | InsightFace `buffalo_l` (ArcFace) at 1–2 fps, faces ≥80 px, yaw ≤45° | **Calibrate per character**: gate at the 5th percentile of within-reference-set similarity. Hosted generations land around 0.42–0.53, so a fixed 0.65 would reject most good takes [CSARKO] (UNVERIFIED figures). |
| Wardrobe, props, set | VLM checklist on 3–5 frames vs the refs | [CSARKO] |
| Prompt adherence | Split the spec into weighted atomic checks; verify against frames; score instruction-following, world coherence and perceptual quality separately | [FIRM 2026-08-22] |
| Unwanted cuts | TransNetV2 shot boundaries vs planned shots | [CUTCRAFT] |
| Text, subtitles, watermark | OCR on sampled frames | [BDPE V-2] |
| Audio present **[FC]** | `ffprobe` audio stream check | [VSB-V] |
| Dialogue | Whisper ASR: es-MX, exact line, no extra words; SyncNet LSE-C/D after lip-sync | [BDPE] |
| Chain health | Laplacian sharpness; ΔE colour drift at tail and head | [BDPE] |
| Verdict | **PASS / EDIT / REROLL**. EDIT = surgical re-prompt for a local flaw; REROLL for any structural flaw. | [COOKBOOK autonomous video] |

### 6.10 Retry protocol

- **Classify the failure:** input-face / prompt / output-video / output-audio / mode-mismatch / infra (§1.6). A failure in under 10 s means a filter: rewrite or re-route, don't re-run [HIGGS].
- **Input-face → re-route** (§6.2 rule 3); never re-run the same image on Replicate **[FC]**.
- **Change one variable per retry:** camera, lighting, motion, or reference role [EMILY retake-protocol].
- **Conservative retry template:** "[Reference role]. Preserve [identity]. One action: [verb/consequence]. Camera: [single move]." [EMILY]
- **Per-shot attempt budget,** then escalate to a human. Repeated failures can mean the model is weak at the shot, not that the prompt is wrong.
- **Log per take:** provider, model ID and version hash, every parameter, seed (or the seed recovered from logs), input hashes, output hash, error text, latency and Replicate metrics.

### 6.11 Lint lists (store as data)

| List | Entries |
|---|---|
| `banned_video` | fast; photorealistic; real person; photographic portrait; 8K; 4K; masterpiece; ultra-detailed; cinematic (in found-footage mode); grainy; VHS; pitch black; glow; glimmer; glint; director, celebrity and brand names |
| `soft_video` **[FC]** | drone; FPV (warn → suggest "aerial flythrough"; not a hard block [SD25G][CFDOC25]) |
| `age_words` (video: block; images: replace with explicit adult phrasing) | child; kid; teen; teenager; boy; girl; minor; schoolgirl; schoolboy; student; school uniform; young (video only) |
| `homographs` | tearing; shoot; draw; break; pound; snap |
| `violence_raw` (rewrite as aftermath or physics) | kill; stab; gore; attack; shoot; torture; mutilate |
| `negations` | Flag any "not/no/never" outside the §2.7 whitelist |
| `multi_camera` | Flag more than one camera verb per beat |
| `emotion_words` | afraid; scared; terrified; sad; angry → require a physical expansion from the lookup |
| `param_leak` | seconds of total length; "16:9"; "720p"; "24fps"; "with audio"; `--` flags |

Sources: [HIGGS][VSB][MOTIONMAX][EMILY][THESOURCE][PICASSO][MAYST][COMFY].

### 6.12 Vertical 9:16 teasers

- **Masters are 16:9.** Horizontal output gets much less unwanted subtitling. Over-long dialogue rambles in about 70% of vertical outputs vs about 30% of horizontal ones (official 2.0 data) [SD20G][BDPE].
- **Cropping a 720p master to 9:16** gives 405×720, a 2.67× upscale to 1080×1920 (too soft for faces).
- **For teaser hero shots:**
  1. Recompose the approved start frame to 9:16 with Nano Banana (same scene, refs and light).
  2. Run 2.5 I2V in vertical.
  3. No native dialogue; strong "no subtitles" line; OCR-check every take [directing report].

---

## 7. Content-policy risks for this story, and safe phrasing

### 7.1 Where the filters sit

| Stage | Filter | Notes |
|---|---|---|
| Nano Banana (Replicate) | Google safety and child-safety filters. Pro exposes `safety_filter_level`. No `person_generation` input on Replicate; which setting Replicate uses is UNVERIFIED. | `IMAGE_SAFETY` is tunable; `PROHIBITED_CONTENT` is not. Children are rejected unless `allow_all` or allowlisted (Vertex) [VERTEXRAI]. The cookbook excludes children "as Nano Banana can't generate images of them in EEA" [COOKBOOK]. |
| Seedance input | Face filter on images (§1.4), including AI faces; bypassed only via the virtual-avatar library [CFDOC25][VSB-S]; prompt intent filter | The filter is semantic, not a keyword list. Stacked cues (weapon + injury + crime + minor + institution) trigger refusals [MINDST][EMILY]. |
| Seedance output | Video and audio output checks | The most common horror failure is the output filter. Some prompts accepted on 2.0 are rejected on 2.5 [MINDST][COMFY]. |
| Celebrities and IP | Blocked since Feb 2026 (after letters from Disney, Paramount and the MPA) | [MAYST] |
| ElevenLabs Voice Design **[FC]** | Refuses voices that read as a child | [VSB-V] (FIELD) |

### 7.2 Story-specific rules

**1994 graduates (adults).**
- **Images:**
  - Lead with "adult" plus an explicit age ≥18, and add adult cues. Better still, cast them visually as early twenties, as live-action productions do.
  - Replace "school uniform / pleated navy skirt / prepa student" with "graduation-day clothes: white blouse, dark slacks" or 1994 casual wear. The current wording reads as schoolgirl and minor-adjacent [image report].
  - Drop "child, minor" from negative lists; pasting these tokens can prime the minor classifier [image report] (trigger behaviour UNVERIFIED).
- **Video prompts:** **no age words at all**, including "young". Refer to people by role and wardrobe ("the woman in the black denim jacket"). Age words tighten the filter sharply [HIGGS]. Exact ages and skin-tone strings correlate with E005 on Replicate [MOTIONMAX] (UNVERIFIED).
- **Voice Design:** "Male, early 20s / young adult", never "17–19". Child-sounding voices are refused anyway (§7.1).

**Blood trickle.**
- One thin trickle ("a thin dark-red line from her left nostril"), no wounds, no pooling.
- Never in the same shot as weapons, police, "crime" or age words.
- A 2.5 horror case with "Dark blood drips from her lips… extreme close-up, slow motion" ran on OpenArt [GOODCASE]. Heavy blood and visible severe wounds are blocked [THESOURCE][PICASSO].
- The current project rule ("no gore, a thin nosebleed at most") fits.

**Ghosts.** "A pale, motionless figure, out of focus, at the end of the hall"; wet hair; a silhouette in the doorway. Imply rather than show; avoid gore effects.

**Police.**
- "Two uniformed officers sweep flashlights across the tunnel mouth."
- No drawn weapons, no "shoot", "gun" or "crime scene" stacking.
- No readable insignia or real agency names. Text is a weak spot anyway: add any text in post.

**Death and violence.** Use aftermath and physics: "overturned chair, a dark smear trailing toward the shaft", not the act itself. Keep injuries off-frame or implied by sound and shadow [seedance-api report][EMILY].

**Objects that imply children** (e.g. "child-sized shoe") are untested; check them against the filter.

**Rewrite table:**

| Risky | Safe |
|---|---|
| "another boy stands with his back to camera" | "another man stands with his back to camera" |
| "18-year-old prepa student in school uniform" | (image) "an adult woman, 19, in 1994 graduation-day clothes"; (video) "the woman in the white blouse" |
| "monster tears him apart" | "the flashlight drops and rolls; the beam settles on an empty boot; a wet dragging sound fades" |
| "he gets shot" | do not depict; cut on sound in the edit |
| "photorealistic real person close-up" (Seedance) | delete; identity lives in the start frame or the avatar reference |
| "drone shot over the mine" | "aerial flythrough over the mine" (style preference; not an E005 cause **[FC]**) |
| "she is terrified" | "her breath catches; she steps back half a pace; the flashlight shakes" |

### 7.3 Never do

- Moderation-evasion techniques: grids, red crosses, noise or sketch filters over faces [ZEROLU][seedance-api report]. These conflict with provider terms, and the Gemini API Additional Terms forbid bypassing safety features [image report].
- `use_virtual_avatar` on a photo of a real person; it is a declaration that the person is AI-made and rights-cleared [CFDOC25][VSB-S] **[FC]**.
- Real-person photos as references [GPOL].
- Celebrity, director or brand names.

### 7.4 Distribution

- YouTube added an "unsatisfying or off-putting… designed to shock" demonetisation bucket in July 2026; recurring characters with distinct storylines remain allowed [CSARKO] (UNVERIFIED). This is material risk for an AI horror channel.
- Keep SynthID and C2PA intact (all Gemini image outputs carry them [GCBP]) and disclose AI use.

---

## 8. Open questions, UNVERIFIED items, and the test pack

**P0: settle before building more (these decide the architecture)**

1. **Face routing test [FC: reframed].** Replicate Seedance refusing photoreal faces is now treated as fact [VSB-S][COMFYPR]. Test:
   - **(a) Replicate 2.5, 480p:** which *face-light* framings pass (half-shadowed profile, three-quarter-away, wide small face, back of head, no face). Record the error text and time to failure.
   - **(b) Cloudflare 2.5 with `use_virtual_avatar:true`:** frontal close-up and two-shot from Nano Banana. Measure how far the output departs from the start frame, and whether reference mode with "Use Images 1 to N in order as keyframes" restores composition.
   - **(c) Veo 3.1 and Kling v3 Omni** on the same frames: face acceptance, Mexican Spanish speech quality, horror moderation.
   - **(d)** The ModelArk `asset://` route, if an account exists.
   - The results set the face routing in §6.2.
2. **Account access:** Replicate access to `bytedance/seedance-2.5` and a Cloudflare Workers AI account (Seedance models, pricing, REST call path from Python) for the team's plan and region.
3. **Live schemas** of `bytedance/seedance-2.5`, `-2.0-mini` and `google/nano-banana-2.1`:
   - `thinking_level`? `seed`? A safety field? Prompt maxLength?
   - Are unknown keys ignored or rejected on Replicate?

**P1: prompt behaviour**

4. 2.5 prompt cap on Replicate: send a 2,100-character prompt.
5. Dialogue syntax on 2.5: `"…"` (default) vs `{}`. Mexican accent stability across 5 shots. Spanish words per second, and whether tight durations trigger a language switch.
6. Is `image` + `reference_videos` + `reference_audios` possible on 2.0? How close does `[Audio1]` voice conditioning get to the ElevenLabs voice?
7. Lip-sync arms A–E (§5.9). `sync_mode` `cut_off` vs `silence` with padded audio.
8. 2.0 timestamps vs Shot labels.
9. Dark scenes: CLEAN_HEAD plus a readable frame and grading in post, vs prompting the darkness directly. Order of the FORMAT and CLEAN_HEAD lines.
10. Subtitle and rambling rates on 2.5, 9:16 vs 16:9 (the official figures are for 2.0).
11. Does a floor-plan lock line measurably reduce axis flips, especially on the avatar route?
12. Nano Banana: two views per person vs one; whether reference order matters; Pro vs 2.1 for identity anchors.

**P2: facts to re-check**

- **Seedance:**
  - The Replicate 2.5 go-live date.
  - Mini schema and price ($0.04/$0.09, two secondary sources).
  - Mono vs stereo audio.
  - Draft mode on Replicate (absent from the 2026-10-05 schema).
  - 2.5 at 1080p on ModelArk: native or upscaled?
  - 2.0 `reference_images` ≤9 vs "1–4, no 1080p".
  - Whether "photorealistic" or large inputs raise E005.
  - The official violence and minors rules (none found).
  - The "Trusted Outputs" Seedream path.
  - Dreamina's handling of its own generated faces.
  - The Replicate blog date.
  - SYNTX parameter mapping.
  - The 11-language list for 2.5.
  - First/last-frame ratio mismatch: stretched or cropped.
  - Whether ModelArk `asset://` with `role:first_frame` keeps the exact opening frame.
- **Nano Banana:**
  - Whether `google/nano-banana` still serves after 2026-10-02.
  - What Replicate does with `nano-banana-2` after 2026-10-29 (Vertex runs to 2027-05-28).
  - Which `person_generation` setting Replicate uses.
  - The NB2 Lite reference cap (3 vs 14).
  - Exact 2K and 4K pixel sizes.
  - The 2.1 4K price ($0.1134 on Replicate vs $0.0756 from Google).
  - 2.1 character and object caps.
  - The release date of the Seedream 4.5 aspect enum and of NB2 Lite.
- **ElevenLabs:**
  - Whether v4 rejects or ignores `style`/`speed`/`use_speaker_boost`.
  - Whether v4 stability is continuous.
  - Whether Spanish-language tags work.
  - Whether v2 reads brackets aloud.
  - API price per 1K characters ($0.08 vs $0.18) and the launch-promo terms.
  - Shared-voices accent and locale strings for Mexican Spanish.
- **Lip-sync:**
  - Whether `lipsync-2` / `-2-pro` are active or deprecated.
  - The price of `lipsync-2`, HeyGen and Kling lip-sync.
  - Whether `sync-3` is on Replicate.
- **Research figures not opened:** arXiv 2608.16717 (180-degree weakness) and 2608.22725 (filtered context); the keep-rate and identity-similarity figures in [CSARKO]; the MindStudio lip-sync and identity percentages.

---

## Appendix A: repo mismatches (checked locally 2026-10-07; not re-checked in the fact-check pass)

| File | Finding | Fix |
|---|---|---|
| `/home/user/serie-factory/prompts/templates/image/{character,location,start_frame,member_1994,thumbnail}.yaml` | `model: google/nano-banana` (EOL) | `google/nano-banana-2.1`, with `google/nano-banana-pro` for hero refs; `resolution: 2K`, `output_format: png`, `allow_fallback_model: false` (Pro only) |
| `/home/user/serie-factory/series/la-garganta/prompt_en.yaml` (l.33) | negative list includes `child, minor`; Nano Banana has no negative input | drop the tokens; remove the Negative block from image API JSON; rewrite rules as semantic positives |
| same file (l.129, l.135) and `member_1994.yaml` | "prepa graduate… school uniform" | adult cues and graduation-day or casual clothes (§7.2) |
| `/home/user/serie-factory/prompts/out/la-garganta/1/p1-1.02-frame.md` | "another **boy**"; generic "Use the attached reference images…"; long "Strictly: no…" negation list | "another man"; ordinal roles ("Image 1 = tunnel, Image 2 = Lupita…") with `image_input` in the same order; positive phrasing |
| `/home/user/serie-factory/prompts/templates/video/shot.yaml` | `aspect_ratio: "16:9"` for I2V; a `negative:` block that no Seedance API accepts; people re-described in I2V; no per-version grammar | `adaptive`; whitelist negatives inside the prompt; lock line only; separate 2.0 and 2.5 compilers (§2.2); **[FC]** add `provider`, `face_visible` and `virtual_avatar` fields and `quote_style: double_quotes` |
| `/home/user/serie-factory/fabrica/voice.py` (l.39–42) | `style` 0.25 / 0.15 / 0.7 / 0.9; `seed` never sent (per voice report); only `request-id` read | per-model settings (§5.2, §5.4); send `seed` and include it in the cache key; `language_code:"es"` for v3/v4 only; log `character-cost`; **[FC]** use `previous_request_ids` on v4 only |
| `/home/user/serie-factory/prompts/templates/voice/design.yaml` | `eleven_multilingual_ttv_v2`; free-form description | `eleven_ttv_v3`; official format (§5.7); validate 20–1000 and 100–1000 character lengths; fixed seed |
| Script stage / `prompts/templates/voice/line.yaml` | all part-1 lines `delivery: normal` | emit deliveries (whisper, quiet fear, shout, scream, crying) → tags |
| `/home/user/serie-factory/docs/COSTS.md` | Sync row empty (per voice report) | `sync/lipsync-2-pro` $0.08325/s (2026-09-14; re-check); **[FC]** add Cloudflare Seedance rows (2.5 same as Replicate; 2.0 cheaper) |

---

## Appendix B: sources (URL, date)

"n/d" means no date was visible. "SE" means read via a search-engine extract only. "mirror" means the official text was read through a GitHub copy. **"FC-read"** marks sources opened in the 2026-10-07 fact-check.

**New in the fact-check [FC]**
- [CFDOC25] Cloudflare docs, model catalog `bytedance-seedance-2.5.json` (created_at 2026-08-07; pricing, schema, `use_virtual_avatar`, examples). OFF. FC-read. https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/catalog-models/bytedance-seedance-2.5.json
- [CFDOC20] Cloudflare docs, `bytedance-seedance-2.0.json` (created_at 2026-05-22; pricing). OFF. FC-read. https://github.com/cloudflare/cloudflare-docs/blob/production/src/content/catalog-models/bytedance-seedance-2.0.json
- [VSB-S] visualsandbox `vsb-seedance` SKILL.md (face tests dated 2026-10-07). FIELD. FC-read. https://github.com/visualsandbox/skills/blob/main/skills/vsb-seedance/SKILL.md
- [VSB-V] visualsandbox `vsb-video` SKILL.md ("People who talk", prices "October 2026"). FIELD. FC-read. https://github.com/visualsandbox/skills/blob/main/skills/vsb-video/SKILL.md
- [LV] Loop-Vesper Replicate setup notes (Seedance 2.5 limits and 422 constraints), n/d. FIELD. FC-read. https://github.com/tensalir/Loop-Vesper/blob/68e387386a0a36b40f77fe631fd1f86944ce2282/docs/integrations/REPLICATE_SETUP.md
- [MPEDIA] modelpedia Replicate model records (status, last_updated 2026-07-31 → 2026-10-07). FC-read. https://github.com/assistant-ui/modelpedia/tree/main/packages/data/providers/replicate/models
- [VIVI] vivijure-cf `params.ts` (7003 PrivacyInformation; avatar flag), n/d. FIELD. FC-read. https://github.com/skyphusion-labs/vivijure-cf/blob/2e45116f68e88019424193d16ea052eb97365786/modules/cf-seedance/src/params.ts
- [RESCI] ReScienceLab scene-video notes, 2026-09-25 (Ark pricing anecdote). FIELD. https://github.com/ReScienceLab/super-prototyping/blob/fa11600240d870c8cecdf7f118d4b660c831668a/docs/2026-09-25-scene-video.md
- [EL-STITCH] ElevenLabs "Stitching multiple requests", mirror refreshed 2026-10-06. OFF. FC-read. https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/request-stitching
- [EL-V4CAP] ElevenLabs "Eleven v4" capability page (accent FAQ, Voice Design note), mirror. OFF. FC-read. https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4
- [EL-WHATV4] ElevenLabs help center "What is Eleven v4?", mirror. OFF. FC-read. https://elevenlabs.io/docs/help-center/product/core-capabilities/text-to-speech/what-is-eleven-v4
- [EL-INTRO] ElevenLabs docs intro (credits), mirror. OFF. https://elevenlabs.io/docs/overview/intro

**Seedance: official**
- [SD25G] BytePlus "Seedance 2.5 prompt guide", doc 2607689, updated 2026-08-07. https://docs.byteplus.com/en/docs/ModelArk/2607689. Mirrors captured 2026-08-09 (FC-read): https://raw.githubusercontent.com/JPG-GITY/byteplus-docs-sync/main/skill/references/video-seedance-2.5-prompt-guide.md and https://raw.githubusercontent.com/lukasersil/seedance-25/main/references/official-spec.md (= [SD25SPEC]). Chinese PDF (2026-08-07): https://raw.githubusercontent.com/Jdaroro/awesome-seedance-2x-prompts/078d4d244a7b22b46156358f5afcb5fce3b4077d/docs/official-pdfs/zh-CN/
- [SD25PE] Official sd25-pe skill, verbatim mirror, 2026-08-09 (FC-read l.227, l.829). https://raw.githubusercontent.com/JPG-GITY/byteplus-docs-sync/main/skill/references/seedance-2.5-prompt-optimizer-SKILL.md
- [SD25RES] BytePlus "How to write better Seedance 2.5 prompts", n/d, SE. https://ai.byteplus.com/resources/how-to-write-better-seedance-2-5-prompts
- [SD20G] Seedance 2.0 prompt guide, doc 2222480, PDF snapshot ≈2026-07-20. https://docs.byteplus.com/en/docs/modelark/2222480
- [SD10G] Seedance 1.0 guide 1587797, n/d, SE. https://docs.byteplus.com/en/docs/modelark/1587797
- [BDPE] ByteDance agentkit-samples `byted-ark-seedance-pe` (troubleshooting V1.7 2026-05-14). https://github.com/bytedance/agentkit-samples/tree/main/skills/byted-ark-seedance-pe
- [BPASSET] BytePlus private virtual portrait library 2333565, n/d, not fetched. https://docs.byteplus.com/en/docs/ModelArk/2333565
- [ARKAPI] ModelArk API doc (UpdatedTime 2026-08-24), as quoted in https://github.com/Reid-Surmeier/Image-generation-pipline-copy/blob/main/seedance/docs/research/seedance-comfyui-research.md
- [SD20P] Seedance 2.0 paper, arXiv 2604.14148, 2026-04-15. https://huggingface.co/papers/2604.14148
- [SEEDBLOG] Seed blog, Seedance 2.5, 2026-07-31 (blocked in FC). https://seed.bytedance.com/en/blog/one-take-creation-flexible-referencing-introducing-seedance-2-5

**Seedance: Replicate and providers**
- [RS25] Replicate `seedance-2.5` schema, cortex fixture (FC-read). https://github.com/aj-archipelago/cortex/blob/main/tests/fixtures/priority-replicate-schemas.json
- [GFV] genfeed Replicate variants fixture, captured 2026-10-05 (FC-read: Seedance, Veo 3.1, Kling v3, p-video). https://github.com/genfeedai/genfeed.ai/blob/1537ead8e2124a51e9e81d93eca359354e1f753a/packages/pricing/src/reviewed-rates/replicate-variants.fixture.ts
- [GFR] genfeed reviewed rate sheet, verifiedAt 2026-10-06 (FC-read). https://github.com/genfeedai/genfeed.ai/blob/master/packages/pricing/src/reviewed-rates/reviewed-rate-sheet.data.ts
- [RS20] `seedance-2.0` schema snapshot, 2026-06-05 (FC-read). https://github.com/alikebrahim/ai_generation_ui/blob/fe533e94df24b537c35c4c386dc95d544f7ca40b/schemas/replicate/seedance-2.0.json
- [TREG] treg Replicate catalog, 2026-09-01. https://github.com/superdesigndev/treg/blob/main/src/treg/catalog/replicate.extended.yaml
- [ADTOOL] Video provider freshness, 2026-09-07 (FC-read). https://github.com/AdToolAI/caption-cloud-magic/blob/main/docs/video-provider-freshness-2026-09-07.md
- [JUSPAY] Schema-verified, 2026-07-19. https://github.com/juspay/director/blob/main/src/generators/replicate-reference.ts
- [RIFF] Live verification, 2026-08-29 (FC-read). https://github.com/davidrd123/riff-mcp/blob/main/LIVE_VERIFICATION.md
- [CFCAT] Cloudflare catalog datamining (2.5 schema-input, FC-read). https://github.com/Cloudflare-Mining/Cloudflare-Datamining/blob/main/data/middlecache/v1/workers-ai-model-catalog/models/bytedance/seedance-2.5/schema-input.json
- [RX] Replicate on X, 2026-04-08 (blocked in FC). https://x.com/replicate/status/2041933843494793238
- [RBLOG] Replicate blog, ≈Apr 2026 (date UNVERIFIED). https://replicate.com/blog/seedance-2
- [RDOCS] Replicate docs, n/d. https://replicate.com/docs/topics/predictions/input-files · /output-files · /rate-limits
- [CFACQ] BusinessWire, 2025-11-17. https://www.businesswire.com/news/home/20251117400765/en/Cloudflare-to-Acquire-Replicate-to-Build-the-Most-Seamless-AI-Cloud-for-developers
- [COMFY] ComfyUI `nodes_bytedance.py`, fetched 2026-10-07 (FC-read: 2.5 1080p, Draft, virtual library, error codes, tooltips). https://github.com/comfyanonymous/ComfyUI/blob/master/comfy_api_nodes/nodes_bytedance.py
- [COMFYPR] ComfyUI_frontend PR #19638, merged 2026-09-30 (FC-read). https://github.com/Comfy-Org/ComfyUI_frontend/pull/19638
- [COMFYDOC] Comfy-Org/docs PR #1785, 2026-09-29. https://github.com/Comfy-Org/docs/pull/1785
- [ARK74] ark-mcp PR #74, 2026-09-24 (FC-read). https://github.com/byteplus-sa/ark-mcp/pull/74
- [ARK83] ark-mcp PR #83, merged 2026-10-03 (FC-read). https://github.com/byteplus-sa/ark-mcp/pull/83
- [TECHNODE] technode, 2026-07-31. https://technode.com/2026/07/31/bytedance-launches-seedance-2-5-video-generation-model/
- [EVOLINK] evolink, 2026-08. https://evolink.ai/blog/seedance-2-5-api-status
- [CELLCOG] cellcog, 2026-08-22, SE. https://cellcog.ai/blog/seedance-2-5-pricing/
- [MAJIK] koskeller/majik (schemas swept 2026-05-05 and 2026-08-29). https://github.com/koskeller/majik
- [AUTOSHOW] autoshow config ("verified Sept 11"). https://github.com/ajcwebdev/autoshow-cli/blob/main/src/cli/commands/setup-and-utilities/models/video-config.json
- [POLL] pollinations registry (2.5 addedDate 2026-08-09; Mini 2026-08-14 with $0.04/$0.09) (FC-read). https://github.com/pollinations/pollinations/blob/main/shared/registry/image.ts
- [ATLASMINI] AtlasCloud, June 2026. https://www.atlascloud.ai/blog/ai-updates/seedance-2.0-mini-overview

**Seedance: practitioner (FIELD)**
- [NICK] 2026-09-05 (FC-read). https://github.com/nickonai/video-agents/blob/main/references/seedance-2.5.md
- [ZEKE] n/d. https://github.com/zeke/helicopter-skill
- [ATHA] n/d. https://github.com/haft-sh/athabasca-skills
- [RECOUP] 2026-09-14. https://github.com/recoupable/skills/pull/145
- [OPENSTORY] 2026-09-29. https://github.com/openstory-so/openstory/issues/1927
- [ARCREEL] 2026-08-31. https://github.com/ArcReel/ArcReel/issues/2249
- [MOKU] PR #21, 2026-09-30. https://github.com/moku-labs/ai/pull/21
- [VSB] n/d (= [VSB-S]). https://github.com/visualsandbox/skills/blob/main/skills/vsb-seedance/SKILL.md
- [REALAMAN] n/d. https://github.com/realaman90/ai-film-skills/blob/main/reference/seedance.md
- [MOTIONMAX] verified 2026-05-15. https://github.com/kameleyon/motionmax/blob/3503d6d1702259ad2579a09128abb0af4137fefb/worker/src/services/replicateSeedance.ts
- [BACKLOT] 2026-07-08. https://github.com/zakasalaheddine/backlot
- [CLSAND] n/d. https://github.com/clsandoval/seedance-skill
- [AIMV] n/d. https://www.aimusicvideo.com/blog/seedance-e005-input-flagged-as-sensitive-fix
- [HIGGS] 2026-07..09 (FAILURE-MODES measured 2026-08-09). https://github.com/OSideMedia/higgsfield-ai-prompt-skill
- [EMILY] verified 2026-08-01, 2026-09-07, 2026-09-26. https://github.com/Emily2040/seedance-2.0
- [ANIL] n/d. https://github.com/Anil-matcha/awesome-seedance-2.5-api-prompts
- [FALRM] n/d. https://github.com/fal-ai/seedance-2.0-api
- [TAPC] 2026-05-30 / 2026-08-03. https://github.com/anymouschina/TapCanvas
- [PJACE] 2026-08-04. https://raw.githubusercontent.com/lukasersil/seedance-25/main/references/proven-fixes.md
- [LUKSURF] 2026-08-04. https://raw.githubusercontent.com/lukasersil/seedance-25/main/references/surface-profiles.md
- [SMIXS] 2026-07-31 guide basis. https://github.com/smixs/visual-skills/blob/main/video/references/seedance-25.md
- [MINDST] n/d, SE. https://www.mindstudio.ai/blog/seedance-2-5-review-guide
- [THESOURCE] 2026-04-15, SE. https://thesource.com/2026/04/15/seedance/
- [PICASSO] n/d, SE. https://blog.picassoia.com/seedance-2-0-content-filter-what-gets-blocked-and-why
- [ZJT] n/d. https://github.com/jeffstric/ZJT/blob/main/docs/web/content_violation_frontend_notify.md
- [MAYST] n/d. https://github.com/maystudios/claude-skills/blob/main/seedance/references/access-and-specs.md
- [TCRUNCH] 2026-03-26. https://techcrunch.com/2026/03/26/bytedances-new-ai-video-generation-model-dreamina-seedance-2-0-comes-to-capcut/
- [ZEROLU] "May 2026 Update", cited only as do-not-use. https://github.com/ZeroLu/seedance2.0-how-to/blob/main/how-to-use-real-face-in-Seedance2.0.md
- [GOODCASE] Aug–Sep 2026. https://goodcase.ai/cases/seedance-shot-1-0-0-1-2s-image-1-face-and-outfit-matching-reference-lying-in-b6d9ef0e370e
- [OPENMONT] n/d. https://github.com/calesthio/OpenMontage/blob/9327439db69021ab4b0e2776729bf3b58fdb5a87/.agents/skills/seedance-2-5/reference/techniques.md
- [CSARKO] 2026-09-16. https://github.com/csarkosh/csarko.sh/blob/4cc2b7a4fb937789d0773e5263f47d50ac65dba7/docs/published/2026-09-16-ai-short-film-generation.md
- [MANJU] 2026-09-19. https://github.com/lixiaoxiao9888-create/manju-laoli-skill/blob/079df685f7cf2f0de635362bd359c233db38f9fe/short-drama-director/references/seedance-render-engine.md
- [VENICE] n/d. https://github.com/jordanurbs/venice-video-harness/blob/bcfb9194ebed41c02f98773e991e8e9c9ce8a798/.agents/agents/prompt-engineer.md
- [WAVESPEED] n/d, SE. https://wavespeed.ai/blog/id/posts/blog-fix-flicker-jitter-seedance-2-0/
- [VIDEOAI] n/d, SE. https://videoai.me/blog/seedance-2-0-limitations
- [SAGNIK] n/d, SE. https://sagnikbhattacharya.com/blog/seedance-2-lip-sync-talking-head
- [HEYUAN] 2026-07-11, SE. https://www.heyuan110.com/posts/ai/2026-07-11-seedance-2-prompt-guide/
- [ATLASCMP] n/d, SE. https://www.atlascloud.ai/blog/guides/seedance-vs-kling-vs-sora-vs-veo
- [OPUS] n/d, SE. https://www.opus.pro/blog/one-shot-continuous-video-seedance
- [A1] 2026-05-12, updated 2026-07-24. https://github.com/luquitared/mograph-cli/blob/main/docs/workflows/voice-via-audio-ref/README.md

**Research papers** (https://huggingface.co/papers/<id>)
- [CUTCRAFT] 2609.08275, 2026-09-15
- [CINECREW] 2609.07720, 2026-09-07
- [WANPE] 2609.30221, 2026-09-25
- [FILMBENCH] 2607.24241, 2026-07-27
- [OSOD] 2605.22144, 2026-05-21
- [FIRM] 2608.21839, 2026-08-22

**Images**
- [NBCARD] DeepMind NB 2.1 model card, 2026-10-06, SE. https://deepmind.google/models/model-cards/nano-banana-2-1/
- [NB21] ai.google.dev NB 2.1 model page, 2026-10-06, SE. https://ai.google.dev/gemini-api/docs/models/gemini-nano-banana-2.1
- [NB21NEWS] 2026-10-06. https://www.neowin.net/news/google-launches-nano-banana-21-with-better-editing-and-subject-consistency/ · https://the-decoder.com/googles-new-image-model-nano-banana-2-1-generates-better-images-for-less-money/
- [GDEPR] Deprecations page, SE. https://ai.google.dev/gemini-api/docs/deprecations
- [LITELLM] fetched 2026-10-07 (FC-read: deprecation dates, prices). https://github.com/BerriAI/litellm/blob/main/model_prices_and_context_window.json
- [COOKBOOK] Gemini cookbook (Get_Started_Nano_Banana, last commit 2026-10-06; FC-read: 1K sizes, 3/14/6 caps). https://github.com/google-gemini/cookbook
- [GCBP] Google Cloud blog, 2026-03-06. https://cloud.google.com/blog/products/ai-machine-learning/ultimate-prompting-guide-for-nano-banana
- [GCBNB2] Google Cloud blog, 2026-02-27. https://cloud.google.com/blog/products/ai-machine-learning/bringing-nano-banana-2-to-enterprise
- [GDEVIMG] n/d, SE. https://ai.google.dev/gemini-api/docs/image-generation
- [GRECIPE] n/d. https://github.com/GoogleCloudPlatform/generative-ai/blob/main/gemini/nano-banana/nano_banana_recipes.ipynb
- [GENAI] google-genai 2.28.0, 2026-10-02. https://pypi.org/project/google-genai/
- [RPUB] all-the-public-replicate-models@1.686.0, 2026-04-21. https://github.com/replicate/all-the-public-replicate-models
- [TREGNB] checked 2026-09-14. https://github.com/superdesigndev/treg/blob/main/src/treg/catalog/replicate.yaml
- [PUTER] fetched 2026-10-07 (FC-read: NB2, NB2-Lite and Pro schemas; no NB 2.1 entry). https://github.com/HeyPuter/puter/blob/main/src/backend/drivers/ai-image/providers/replicate/catalog.ts
- [APPIFY] 2026-08-07. https://github.com/appifyhub/agent-backend
- [VERTEXRAI] n/d, SE. https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/gemini-image-responsible-ai
- [GPOL] revised 2024-12-17. https://policies.google.com/terms/generative-ai/use-policy
- [QWEN] n/d. https://huggingface.co/Qwen/Qwen-Image-Edit-2511

**Voice.** ElevenLabs official docs were read via the mirror https://github.com/Eyre921/ofiicial-developer-docs, refreshed 2026-10-06 (FC-read: models, TTS convert, TTD with-timestamps, voice design, stitching, v4 pages).
- [EL-V4] https://elevenlabs.io/docs/overview/capabilities/text-to-speech/eleven-v4
- [EL-BP] https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices
- [EL-MODELS] https://elevenlabs.io/docs/overview/models
- [EL-PLAY] https://elevenlabs.io/docs/eleven-creative/playground/text-to-speech
- [EL-API] https://elevenlabs.io/docs/api-reference/text-to-speech/convert
- [EL-TS] https://elevenlabs.io/docs/api-reference/text-to-speech/convert-with-timestamps
- [EL-TTD] https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue and https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert-with-timestamps
- [EL-VD] https://elevenlabs.io/docs/api-reference/text-to-voice/design and https://elevenlabs.io/docs/eleven-creative/voices/voice-design
- [EL-SHARED] https://elevenlabs.io/docs/api-reference/voices/voice-library/get-shared
- [EL-BILL] https://elevenlabs.io/docs/overview/administration/billing
- [EL-SKILL] elevenlabs/skills (PR #133 2026-10-05; PR #130 2026-09-29) (FC-read). https://github.com/elevenlabs/skills/blob/main/text-to-speech/SKILL.md

Secondary voice sources:
- [S16] 2026-09-28. https://github.com/Noble-Collective/Noble-Imprint-Audiobooks/blob/main/docs/ELEVENLABS-MODELS.md
- [S17] 2026-10-02. https://github.com/Godefroy/micdrop/blob/main/website/src/content/blog/elevenlabs-api-pricing-voice-agent/index.mdx
- [S19] n/d. https://github.com/PicsArt/ai-sdk/blob/main/src/vendors/catalog/elevenlabs.ts
- [S20] 2026. https://github.com/discimusdux-ai/ai-tool-stack/blob/main/content/blog/elevenlabs-review-2026.mdx
- [S21] n/d. https://github.com/steipete/sag/blob/main/cmd/speak.go
- [S22] n/d. https://github.com/Trompetilla/Skills/blob/main/skills/shaharsha/elevenlabs-tts/SKILL.md
- [S23] n/d. https://github.com/zapier/connectors/blob/main/apps/elevenlabs/references/elevenlabs-api-gotchas.md
- [S24] n/d. https://github.com/enricoros/big-AGI/blob/main/src/modules/speex/protocols/rpc/synthesize-elevenlabs.ts
- [S25] n/d. https://github.com/TJC-LP/sanzaru/blob/main/src/sanzaru/descriptions.py

**Lip-sync**
- [L1] genfeed Replicate schemas.json (fetchedAt 2026-03-06; FC-read: lipsync-2/-2-pro and NB fields). https://github.com/genfeedai/genfeed.ai/blob/0c507527bedb1e93682dc6c40a5eb4a772a9b913/packages/contracts/src/types/replicate/schemas.json
- [L2] verified 2026-09-14 (FC-read). https://github.com/nodaroai/app.nodaro.ai/blob/main/backend/src/providers/replicate/output-cost.ts
- [L4] 2026-07-11. https://github.com/calesthio/generative-media-skills/tree/main/skills/providers/lip-sync/sync-labs-lipsync
- [L5] n/d. https://github.com/cluely/unmodel/blob/main/docs/surfaces.md
- [L9] 2026-09-27 (= [MPEDIA] record; flag unreliable). https://github.com/assistant-ui/modelpedia/blob/main/packages/data/providers/replicate/models/sync-lipsync-2-pro.json

Working copies of the downloaded captures are in `/tmp/claude-0/-home-user-serie-factory/17cbcadb-7dbd-505a-89c0-869392b98ac1/scratchpad/fc/`.