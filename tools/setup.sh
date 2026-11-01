#!/usr/bin/env bash
# Prepara la sesión para fabricar clips (idempotente). Las versiones están en tools/requirements.txt.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install -q --root-user-action=ignore -r tools/requirements.txt
for t in ffmpeg ffprobe; do command -v "$t" >/dev/null || { echo "Falta $t"; exit 1; }; done
python3 -c "import json; from faster_whisper import WhisperModel; WhisperModel(json.load(open('config.json'))['whisper_model'], device='cpu', compute_type='int8')" >/dev/null
for u in https://www.ted.com https://huggingface.co; do
  [ "$(curl -s -o /dev/null -m 10 -w '%{http_code}' "$u" || true)" = "000" ] && echo "AVISO: sin acceso a $u (Network access del entorno)"
done
echo "Entorno listo"
