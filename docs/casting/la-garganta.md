# Кастинг · LA GARGANTA

> Зона A (продакшн). Промпти — **англійською** для Gemini / Nano Banana. Джерело ознак — `series/la-garganta/bible.yaml`
> (`characters[].visual_dna`, `supporting.los_siete.members`, `locations`). Обличчя затверджує людина (dimaShelest).
> Файли зображень у Git **не** кладемо: `output/refs/la-garganta/…` локально, затверджені — в R2.

## Як працювати

1. **Базовий портрет.** Генеруй 4 варіанти, обери 1 → `output/refs/la-garganta/characters/<id>/base_v1.png`.
2. **Лист персонажа.** Новий запит **з базовим портретом як референсом** (прикріпи зображення) → 3/4, профіль,
   повний зріст, 3 емоції. Якщо сітка 3×2 «пливе» (обличчя різні) — генеруй кожну панель окремо тим самим промптом-панеллю.
3. **Сімка 1994.** Окремий стиль «плівка 1994». **Tomás = Mateo**: генеруй тільки з затвердженим портретом Mateo як референсом.
4. **Локації** — порожні плити 16:9 без людей, плюс стани (меблі на стелі, годинник на 3:17 тощо).
5. **Реквізит-стіли** — фото, що є підказками (C05, C09, C12, C13).
6. Затверджене → запис у `series/la-garganta/refs.yaml` (маніфест: id, файл у R2, промпт, seed, дата).

**Чекліст затвердження обличчя:**
- [ ] усі ознаки `visual_dna` видно;
- [ ] персонаж читається як 18+;
- [ ] четверо відрізняються силуетом і кольором: чорний (Vale), жовтий + червоний (Diego), бордовий (Sofía), синьо-сіра клітинка (Mateo);
- [ ] немає схожості з реальними людьми;
- [ ] немає тексту, логотипів, деформованих рук.

### Спільні блоки (дописуй у кінець кожного промпту)

**[STYLE]**
```
Photorealistic cinematic still, shot on 35mm film, natural skin texture with visible pores, soft directional key light,
muted desaturated palette with deep teal shadows and warm practical highlights, shallow depth of field,
Mexican gothic horror film aesthetic. Original character, not resembling any real person or celebrity.
No text, no letters, no numbers, no watermark, no logo.
```

**[PORTRAIT]**
```
Head-and-shoulders portrait, front-facing, eyes to camera, neutral dark grey studio background, soft even light, 3:4.
```

**[SHEET]** (прикріпи base-портрет)
```
Use the attached image as the identity reference: keep exactly the same face, hairstyle, skin tone, distinguishing marks
and outfit. Create a character reference sheet on a plain light-grey background, 3x2 grid, same lighting in every panel,
no labels or text: (1) three-quarter view head-and-shoulders, (2) left profile head-and-shoulders, (3) full body standing,
front view, (4) {EMOTION_1}, (5) {EMOTION_2}, (6) {EMOTION_3}. 16:9.
```

**[1994]**
```
Candid 35mm film snapshot from 1994, visible film grain, warm faded colors, slight on-camera flash look.
Mexican "prepa" graduates, 18 years old (adults). School uniform: white button-up shirt, navy V-neck sweater or vest,
dark trousers or pleated navy skirt. Authentic early-1990s hairstyles. Original person, not resembling any real person.
No text, no watermark.
```

---

## Герої

### Vale (19) — `vale`
**Base:**
```
Portrait of Vale, a 19-year-old Mexican young woman (adult). Warm olive-brown skin, thick straight dark eyebrows,
intense dark brown eyes, black straight hair pulled into a high messy ponytail with loose strands, a small thin scar
above her left eyebrow. Oversized black denim jacket with frayed, worn sleeves over a plain grey t-shirt.
Expression: guarded and defiant, slight frown. [PORTRAIT] [STYLE]
```
**Sheet:** `[SHEET]` · emotions: `barely contained rage, jaw clenched, a thin line of blood under her nose` ·
`raw terror, eyes wide, frozen` · `quiet determination, chin up`

### Diego (19) — `diego`
**Base:**
```
Portrait of Diego, a 19-year-old Mexican young man (adult). Round friendly face, light brown skin, curly chestnut-brown
hair poking out from under a red baseball cap worn backwards, bright yellow windbreaker jacket.
Expression: big mischievous grin. [PORTRAIT] [STYLE]
```
**Sheet:** `[SHEET]` (повний зріст: `holding a smartphone loosely at chest level, black pants, white sneakers`) ·
emotions: `laughing out loud, eyes squeezed` · `screaming in pure terror` · `awe, mouth open, looking up`

### Sofía (18) — `sofia`
**Base:**
```
Portrait of Sofía, an 18-year-old Mexican young woman (adult). Light brown skin, round thin metal-frame glasses,
long dark hair in a single braid over her right shoulder, burgundy knitted cardigan over a white collared blouse,
canvas tote bag strap across her chest. Expression: focused, analytical, slightly skeptical. [PORTRAIT] [STYLE]
```
**Sheet:** `[SHEET]` · emotions: `deep concentration, eyes lowered as if reading` · `shock, eyes wide, lips parted` ·
`quiet sorrow, eyes wet`

### Mateo (18) — `mateo` · ⚠️ він же Tomás 1994
**Base:**
```
Portrait of Mateo, an 18-year-old Mexican young man (adult). Very pale skin with a faint grey undertone, dark circles
under his eyes, short dark hair parted in the middle in a 1990s style, hair slightly damp as if he had just come in
from the rain. Blue-grey plaid flannel shirt worn open over a plain white t-shirt.
Expression: calm, quiet, unreadable, slightly melancholic. Subtle — he must look like a real living person, not a ghost.
[PORTRAIT] [STYLE]
```
**Sheet:** `[SHEET]` · emotions: `perfect stillness, looking slightly past the camera` · `deep sadness` ·
`a faint, unsettling half-smile`
> Обличчя Mateo — ref і для Tomás 1994, і для подряпаного фото (C09). Затверджуй першим із сімки.

### Renata Ochoa (44) — `renata`
**Base:**
```
Portrait of Renata Ochoa, a 44-year-old Mexican woman, small-town police officer. Tan skin, dark hair in a tight low bun
with a single grey streak at her left temple, a deep vertical frown line between her brows, tired but sharp eyes.
Navy-blue municipal police uniform shirt, a small old silver oval locket on a thin chain at her neck.
Expression: stern, controlled. [PORTRAIT] [STYLE]
```
**Sheet:** `[SHEET]` · emotions: `cold professional authority` · `grief breaking through, eyes wet, lips trembling` ·
`hard resolve`

### Don Arturo Saldívar (62) — `saldivar`
**Base:**
```
Portrait of Don Arturo Saldívar, a 62-year-old Mexican man, beloved small-town mayor. Thick grey hair combed back,
full grey mustache, warm tanned weathered skin, light cream guayabera shirt, a light straw texana cowboy hat.
Expression: warm, fatherly public smile. [PORTRAIT] [STYLE]
```
**Sheet:** `[SHEET]` (повний зріст: `polished boots; a massive silver ring with a black stone on his right ring finger,
hands relaxed at his sides, ring visible but not a close-up`) · emotions: `warm public smile` ·
`cold quiet menace, smile gone` · `sudden fear, color drained from his face`
**Молодий (для фото бригади 1994):** прикріпи base →
```
Same man 32 years younger, age 30: dark hair, dark full mustache, mine foreman in a hard hat with a headlamp.
Keep the same facial structure. [1994]
```

---

## Сімка 1994 — `los_siete`

Для кожного — base у стилі `[1994]` (3:4, напівпортрет) і **мокрий варіант** (для привидів: дзеркало, силуети, скрімери).

**Мокрий варіант** (прикріпи base 1994):
```
Same person, same school uniform, now soaked: hair dripping, skin pale with a grey-blue tint, fine mine dust on the face,
eyes normal (not monstrous), quiet and sad expression, very dark background lit by a single cold flashlight beam.
No gore, no wounds, no blood. [STYLE]
```

| id | Base (вставити в `{…}` перед `[1994]`) |
|---|---|
| `tomas` | **Прикріпи затверджений портрет Mateo:** `Same face as the reference, alive and healthy in 1994: natural warm skin tone, middle-parted hair, blue-grey plaid flannel shirt over the school uniform, smiling at a friend off camera.` |
| `lupita` | `Lupita Herrera: curly dark hair with 90s bangs, large round hoop earrings, laughing, lively.` |
| `chuy` | `Jesús "Chuy" Robles: thick-framed glasses, thin teenage mustache, holding a 1990s VHS camcorder on his shoulder (generic, no brand logos).` |
| `monica` | `Mónica Treviño: tall, straight hair held back with a headband, dark 90s lipstick, confident.` |
| `beto` | `Beto Garza: buzz-cut hair, broad shoulders, a small scar on his chin, grinning.` ⚠️ Його мокрий варіант — обличчя скрімера VHS і хлопець у дзеркалі. |
| `rosa_elena` | `Rosa Elena Fuentes: two dark braids, a small gold cross on a chain, shy gentle smile.` |
| `ivan` | `Iván Castañeda: shoulder-length grunge hair, denim jacket over the school uniform, relaxed.` |

---

## Локації (16:9, без людей)

Дописуй `[STYLE]`, але без рядка «Original character…». Для кожної — 2–4 варіанти, обираємо 1.

| id | Промпт | Стани / варіанти |
|---|---|---|
| `mina` | `Entrance (bocamina) of an abandoned silver mine cut into a steep rocky mountainside above a small Mexican colonial mining town; old wooden support beams, rusted rail tracks leading into darkness, a rusty open gate, no signs. Night, cold moonlight, distant warm town lights far below. Empty, no people. Cinematic wide shot, 16:9.` | **dawn:** `same entrance at dawn, pale golden light, low mist, small pebbles scattered on the ground` · **tunnel:** `narrow mine tunnel, wet rough rock walls, old timber supports, rusted rails, darkness cut by flashlight beams through floating dust` · **flooded:** `lower tunnel with knee-deep still black water reflecting flashlight beams, dripping ceiling` · **collapse:** `tunnel blocked by a wall of fallen boulders, dust hanging in the air` |
| `plaza_reloj` | `Small Mexican colonial mining-town plaza at night: cobblestones, colorful facades with dark windows, a parish church, a stone clock tower with a large white analog clock face with simple bar markers and no numerals, warm yellow streetlights, an old 1980s sedan parked (no brand logos). Empty, no people. 16:9.` | **3:17:** `close view of the clock face; the hour hand and the minute hand both point almost exactly at the 3 o'clock position, nearly overlapping (time 3:17)` |
| `casa_minero` | `Humble old miner's one-room house at night: whitewashed adobe walls, a single metal bed, wooden table and chairs, an oil lamp, a crucifix, a framed old group photograph on the wall; cold flashlight light and red-blue police lights flickering through the small window. Empty. 16:9.` | **ceiling:** `the same room, but all the furniture — bed, table, chairs, lamp — is stuck upside-down to the ceiling, defying gravity; wet bare footprints on the dusty floor leading from the door to where the bed used to stand; water dripping from the bed on the ceiling` |
| `casa_vale` | `Small cramped bathroom in a modest Mexican house at night: an old mirror with worn silvering above a white sink, tiled wall, a single bare bulb. Empty. 16:9.` | **living:** `modest living room at night, old sofa, small TV on a stand with a dark screen, a window showing the dark mountain` · **kitchen:** `small kitchen, a glass of water on the table` |
| `archivo` | `Municipal archive and newspaper library in an old colonial building: tall wooden shelves of bound newspaper volumes, a long wooden reading table, dust floating in beams of daylight from high windows. Empty. 16:9.` | — |
| `cafe` | `Small café on a colonial town plaza by day: large windows facing the plaza, wooden tables, a counter with an espresso machine (no logos), warm daylight. Empty. 16:9.` | **glass:** `the same café, every window exploded and thousands of glass shards hanging motionless in the air` (тест T2) |
| `cuarto_diego` | `Bedroom of a 19-year-old at night: posters with no readable text, unmade bed, a laptop on a desk casting cold blue light, low plaster ceiling with a ceiling lamp. Empty. 16:9.` | — |
| `presidencia` | `Mayor's office in an old colonial municipal building: dark wooden desk, tall shuttered windows with daylight, warm desk lamp, old framed photographs on the wall including one large framed group photo of mine workers. Empty. 16:9.` | **police:** `small-town police station office: old desk with paper files, a two-way radio, corkboard with photos and no readable text, fluorescent light` |
| `panteon` | `Mexican village cemetery at night during Día de Muertos: hundreds of candles, graves covered with bright orange cempasúchil marigold petals and garlands, papel picado without readable text, seven simple wooden coffins in a row covered in marigolds, warm candlelight against deep blue night. No crowds. 16:9.` | — |

---

## Реквізит-стіли (підказки)

| Підказка | Промпт | Де |
|---|---|---|
| C05 / C12 — фото нічної зміни | Прикріпи «молодого Saldívar» → `Faded framed 1994 group photograph of a mine night-shift crew: eight Mexican miners in hard hats with headlamps at a mine entrance at night, the man from the reference in the center as the foreman; each man wears an identical massive silver ring with a black stone, visible as they hold their helmets. Photographed as a framed print hanging on a wall.` [1994] | ч.3 (кабінет мера) — ціле |
| C05 (ч.1) | Те саме фото, редагування: `add a strong reflection glare on the glass over the central figure so his face cannot be seen` | ч.1 (дім шахтаря) |
| C09 — випускники 1994 | Прикріпи base усієї сімки (або по черзі) → `Group photo of seven Mexican prepa graduates in 1994, arm in arm in front of a school wall, smiling.` [1994] → редагування: `rough physical scratches on the photo print completely scratch out the face of the boy in the blue-grey plaid flannel` | ч.3 |
| C13 — фото доказів | `Forensic evidence photograph: close-up of an older man's hand resting on a white sheet, a pale untanned band on the ring finger where a ring used to be. Flat clinical flash lighting. No blood, no injuries.` [STYLE] | ч.2 (still) |
| C07 — VHS-камера | `A dusty 1990s VHS camcorder (generic, no brand logos) lying on wet rocks among seven old school backpacks in a dark mine tunnel, a single flashlight beam.` [STYLE] | ч.4 |
| C13 (ч.4) — трофеї | `An open wooden desk drawer containing several identical massive silver rings with black stones, warm desk-lamp light.` [STYLE] | ч.4 |
