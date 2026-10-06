# LA GARGANTA · Тест-пак Seedance (до старту виробництва)

> Зона A. Мета: до генерації частин 1–2 перевірити, чи тягне Seedance 2.5 п'ять найризиковіших вау-кадрів, і для
> кожного вибрати спосіб виробництва (як є / зі стартовим кадром / з добудовою в монтажі).
> Промпти — англійською. Референси — з `docs/casting/la-garganta.md`.

## Порядок і бюджет

1. **Спершу кастинг:** затвердити base-портрети `vale`, `diego`, `sofia`, `mateo`, `renata`, мокрий варіант `beto`
   і плити локацій `mina` (dawn, tunnel), `cafe`, `casa_minero` (ceiling).
2. **Стартовий кадр** (Nano Banana) для кожного тесту: склади з плити й референсів **той самий стан**, з якого
   стартує рух. Стабільніше, коли предмети вже висять у повітрі, ніж коли модель має їх підняти сама.
3. **Seedance:** image-to-video, 16:9, до 3 спроб на тест. Кожну спробу (seed, параметри, $) пиши в таблицю результатів.
4. **Оцінка:** три шкали по 1–5 (фізика, консистентність, вигляд). **Пройдено** — ≥ 4 за всіма трьома хоча б в одній
   спробі.

| Тест | Розд. | с | Спроб | Макс. $ |
|---|---|---|---|---|
| T1 Левітація каміння | 720p | 8 | 3 | 5,52 |
| T2 Скло в повітрі | 720p | 6 | 3 | 4,14 |
| T3 Меблі на стелі | 720p | 8 | 3 | 5,52 |
| T4 VHS-скрімер | 480p | 6 + 2 | 3 | 2,64 |
| T5 Силуети на телефоні | 480p | 8 | 3 | 2,64 |
| **Разом** | | | | **≈ 20,46** |

**Заодно перевірити** (впливає на кошторис `part1_shotlist.md`):
- мінімальну тривалість кліпу (замов 2 с у T4) і як її рахують;
- максимальну тривалість (10 с?);
- реальну ціну за секунду в рахунку;
- чи можна дати кілька референсів (обличчя + локація) одночасно;
- як тримається головний об'єкт при кропі 9:16 для тизерів.

---

## T1 · Левітація каміння на світанку — ч.1, шот 4.03

**Стартовий кадр** (Nano Banana; прикріпи плиту `mina/dawn` і base `vale`, `diego`, `sofia`, `mateo`):
```
Dawn at the entrance of an abandoned mountain silver mine, low golden mist. Four young adults from the references lie
and sit on the rocky ground, dazed, small trickles of blood under their noses. Hundreds of small grey pebbles hang
motionless in the air around them at different heights. Wide shot, 16:9. [STYLE]
```
**Seedance** (image-to-video, 720p, 8 с):
```
The hundreds of small pebbles floating in the air slowly drift and rotate in place, catching the warm sunrise light;
fine dust glitters in the beams. The four young people stay still, only breathing, one slowly raises her head.
Slow steady camera push-in. Silent, eerie, calm. Photorealistic, cinematic 35mm film look.
Pebbles keep their exact shape and size, no merging, no new objects appearing, gravity does not affect them. No text.
```
**Успіх:**
- камінці не змінюють форму й кількість, обертаються повільно й безперервно;
- у всіх чотирьох видно ДНК: хвіст і чорна куртка, червона кепка й жовта вітровка, окуляри й бордовий кардиган, клітчаста фланель;
- обличчя не «пливуть», камера йде рівно;
- ≥ 6 із 8 с придатні до монтажу.

**Якщо не вийде:** камінці — окремим шаром (згенерувати фон без людей + людей окремо) або 2–3 коротші кліпи з наїздом.

---

## T2 · Уламки скла в повітрі — ч.2, біт 5

**Стартовий кадр** (плита `cafe/glass` + base `vale`):
```
Inside a small café on a colonial town plaza by day. Every window has just exploded inward and thousands of glass shards
hang motionless in mid-air, sparkling. The young woman from the reference stands in the center, fists clenched
(hands not in close-up), furious, a thin line of blood under her nose, her ponytail lifted slightly as if by static.
Medium-wide shot, 16:9. [STYLE]
```
**Seedance** (720p, 6 с):
```
Thousands of glass shards suspended in the air slowly rotate in place, refracting daylight into small rainbow glints.
The young woman breathes heavily, staring ahead, motionless. The camera slowly orbits around her by about 15 degrees.
Total silence. Photorealistic, cinematic. Shards stay sharp solid glass, no melting, no turning into liquid or smoke,
they do not fall. No text, no signs, no logos.
```
**Успіх:**
- уламки лишаються склом і не падають, відблиски правдоподібні;
- обличчя Vale стабільне під час обертання камери, шрам над бровою на місці;
- на вікнах і вивісках немає тексту.

**Якщо не вийде:** нерухома камера + повільний наїзд; сам вибух — окремим шотом 1–2 с або в монтажі (спалах + звук).

---

## T3 · Меблі на стелі — ч.1, шот 7.03

**Стартовий кадр** (плита `casa_minero/ceiling` + base `renata`):
```
Night, a humble miner's adobe room seen from the doorway. All the furniture — a metal bed, a wooden table, chairs,
an oil lamp — is stuck upside-down to the ceiling. Wet bare footprints on the dusty floor lead from the door into the
room. The policewoman from the reference stands in the doorway holding a flashlight, its beam on the floor.
Red-blue police lights flicker through the small window. Wide shot, 16:9. [STYLE]
```
**Seedance** (720p, 8 с):
```
The policewoman slowly steps into the room. The camera tilts up from the wet footprints on the floor to the ceiling,
following her flashlight beam, revealing the furniture stuck to the ceiling. A little dust and a few drops of water fall
down from the bed on the ceiling. The furniture creaks but stays firmly attached to the ceiling the whole time.
Flickering red-blue light from the window. Slow, tense. Photorealistic, cinematic.
No objects falling from the ceiling, no text.
```
**Успіх:**
- меблі весь кліп тримаються на стелі, не сповзають і не «перевертаються» назад;
- пил і краплі падають униз, тобто гравітація для них звичайна;
- ДНК Renata (пучок із сивим пасмом, форма, медальйон) на місці;
- тілт плавний.

**Якщо не вийде:** два шоти — тілт по порожній кімнаті + реакція Renata окремо (тоді кімнату можна дати як still з параллаксом).

---

## T4 · VHS-скрімер у шахті — ч.1, шоти 1.06–1.07 (found-footage)

**Стартовий кадр** (плита `mina/tunnel`):
```
1994 VHS camcorder point of view inside a pitch-black narrow mine tunnel; a single flashlight beam on wet rock walls
and old timber supports; dust in the beam. Low resolution, slight video noise. No on-screen text, no date stamp. 16:9.
```
**Seedance A — наростання** (480p, 6 с):
```
Handheld 1994 camcorder footage: the flashlight beam slowly searches the dark tunnel, trembling slightly with the
operator's breathing. Nothing moves. Water drips. The beam stops on a dark bend of the tunnel. Tense silence.
No text, no date stamp, no people.
```
**Seedance B — обличчя** (480p, **2 с**; стартовий кадр — мокрий варіант `beto` у промені ліхтаря впритул до об'єктива):
```
Extreme close-up in a flashlight beam: a soaked pale young man's face with mine dust on it is suddenly right in front
of the lens, eyes wide open, completely still, water dripping. Handheld camcorder jolts back. No gore, no wounds, no text.
```
**Успіх:**
- A: напруга читається, промінь живий;
- B: обличчя з'являється різко (≤ 0,5 с), а не «проявляється»; ДНК Beto (стрижка, шрам на підборідді) на місці; без гору;
- VHS-вигляд (шум, тремтіння, хроматика, дата як титр) накладаємо в монтажі, тож тест його не оцінює.

**Якщо не вийде:** B як still з різким наїздом + звуковий удар. Скрімер працює на монтажі й звуку, тож це прийнятно.

---

## T5 · Силуети на відео з телефону — ч.2, біти 7–8 (found-footage)

**Стартовий кадр** (плита `mina`, ніч + base четвірки):
```
Night, smartphone video footage, wide shot of an abandoned mine entrance on a mountainside. Four young adults from the
references walk out of the dark entrance towards the camera, lit only by their phone lights. Far behind them, in the
darkness of the tunnel mouth, seven barely visible human silhouettes stand in a loose row. Grainy low-light phone
footage, slight digital noise. No text. 16:9.
```
**Seedance** (480p, 8 с):
```
Low-light smartphone footage. The four young people walk out of the mine towards the camera, talking, unaware.
Behind them, exactly seven dark human silhouettes silently follow at a distance, moving in unison. In the last two
seconds the seven silhouettes stop and slowly turn their heads towards the camera, all at the same time.
The camera slowly zooms in digitally on the silhouettes. Grainy, noisy, realistic phone video. No text.
```
**Успіх:**
- силуетів рівно 7 (мінімум — чітко більше чотирьох і всі однакові силуетом), рухаються синхронно;
- поворот голів одночасний і читається навіть на 480p;
- четвірка не зливається із силуетами.

**Якщо не вийде:** згенерувати окремо четвірку й порожній вхід, силуети додати в монтажі. На телефонному шумі композитинг непомітний.

---

## Результати (заповнюємо після тестів)

| Тест | Спроба | Seed / параметри | Фізика | Консист. | Вигляд | $ | Рішення для виробництва |
|---|---|---|---|---|---|---|---|
| T1 | | | | | | | |
| T2 | | | | | | | |
| T3 | | | | | | | |
| T4 | | | | | | | |
| T5 | | | | | | | |

Висновки → `docs/MEMORY.md` («Що не працює» / уроки), витрати → `docs/COSTS.md` → «Тестові та інші витрати».
