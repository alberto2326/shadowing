---
name: fabricar-clip
description: Procedimiento completo para fabricar UN clip de shadowing (charla TED, 60–120 s, texto verificado con Whisper, sílabas tónicas marcadas) y programarlo en el calendario. Úsala desde nueva-tanda o cuando haya que hacer un clip nuevo.
---

# Fabricar un clip

`tools/shadow.py` hace lo mecánico. Tú decides el tramo, escribes el texto con las sílabas tónicas y los
puntos de escucha.

## 1. Elegir la charla
- TED, ponente **nativo de EE. UU. con americano general** (compruébalo en la página de TED), una sola voz,
  ritmo natural (~120–170 palabras/min), buen sonido, con subtítulos humanos en inglés.

## 2. Descargar y elegir el tramo
```bash
python3 tools/shadow.py download "https://www.ted.com/talks/<slug-de-ted>"   # imprime el <id>
python3 tools/shadow.py srt <id> 0 300                                        # subtítulos con tiempos
```
Elige **60–120 s** que empiecen y acaben en frase completa y se entiendan solos. Los tiempos de los
subtítulos pueden ir ~3 s desplazados: los buenos son los de Whisper.

## 3. Texto real con Whisper
```bash
python3 tools/shadow.py words <id> <inicio-5> <fin+5>
```
Compara con los subtítulos. **Si difieren, manda el audio**; si las dos pasadas de Whisper (`words` y luego
`verify`) no coinciden en una palabra, sigue a los subtítulos. Whisper inventa texto en los silencios y
confunde nombres propios: descártalo y anótalo en `notas`. Escribe las cifras en dígitos (`30,000`, `43%`).

## 4. Ficha `data/clips/<slug>.json`
Slug: `AAAA-MM-apellido-tema-corto`. `start`/`end` aproximados (segundos en la charla); `align` los afina.
```json
{
 "slug": "2026-12-apellido-tema",
 "video_id": "<id>",
 "title": "Nombre Apellido, “Título de la charla” (de qué va el tramo)",
 "source": "TED",
 "url": "https://www.ted.com/talks/<slug-de-ted>",
 "start": 100.0, "end": 180.0,
 "meta": {"hablante": "Nombre Apellido", "charla": "Título", "acento": "Americano general", "tema": "Tema corto en español"},
 "lines": ["<b>Eve</b>rything we do, / we be<b>lieve</b> in <b>chall</b>enging the <b>sta</b>tus quo."],
 "listen_for": "2–3 rasgos en inglés, en HTML",
 "notas": "cómo se verificó el texto y qué diferencias hubo"
}
```
- `lines`: una frase o grupo de sentido por línea (≈1–5 s), palabra por palabra como en el audio.
- `<b>…</b>` solo en la **sílaba tónica** de las palabras con más peso; ` / ` donde hay una pausa breve.
  Las terminaciones (-ing, -ed, -ly, -es, -er, -tion, -ment…) **nunca** llevan el acento: `<b>ask</b>ing`,
  `<b>ques</b>tion`, `<b>quick</b>ly` (no `ask<b>ing</b>`). `add` y `check` rechazan ese error.
- `listen_for`: formas débiles, palabras que se enlazan, contraste de acento, entonación, *gonna*/*kinda*.

## 5. Alinear, construir, verificar y programar
```bash
python3 tools/shadow.py align <slug>      # tiempos de cada línea; avisa si no dura 60–120 s
python3 tools/shadow.py build <slug>      # site/clips/<slug>.mp3 y .json
python3 tools/shadow.py verify <slug>     # vuelve a transcribir el mp3 y lo compara con el texto
python3 tools/shadow.py add <slug>        # primer día libre (o --fecha AAAA-MM-DD)
```
- Si `align` deja líneas sin coincidencia, corrige el texto o amplía `start`/`end` y repite.
- `verify --force` solo si las diferencias son errores del reconocedor ya revisados, explicados en `notas`.
