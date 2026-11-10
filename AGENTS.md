# AGENTS.md — この局を運用するAIへ

このリポジトリは「局」です。`site/`(プレーヤー)が `station.json`・`episodes.json`・`episodes/*.json`・音声を読んで番組として再生します。ビルド機構はありません。

## 毎朝の流れ (pipeline/run_daily.py)

1. `collect.py` — `station.json` の `sources` からRSS等を集めて候補JSON化
2. `script.py` — 台本 `episodes/<日付>.json` を生成 (下記「台本生成の接続」参照)
3. `assemble.py` — `station.json` の `voice` 設定で行ごとにTTS→連結、`lines_timed`/`segments` を台本に書き戻し、BGMをダッキングして `audio/<日付>.mp3` 生成
4. `publish.py` — `episodes.json` 更新、`dist/` を構築(site + 台本 + 直近 `keep_days` 日分の音声)

## 台本生成の接続 (サービス化の契約)

**契約は1つだけ: `episodes/<YYYY-MM-DD>.json` が main ブランチにあれば、その日に放送される。**

日次ワークフローは実行時にこのファイルを確認し:
- **ある** → 外部サービスが生成済みとみなし、音声化+公開のみ行う (`--script external` 相当)
- **ない** → 内蔵生成にフォールバック (`GEMINI_API_KEY` あればGemini、なければ定型台本)

つまり台本生成サービスは「このJSONを main に置く」ことだけを実装すればよく、置き方は自由:

- 同リポジトリへ直接 push (bot PAT / GitHub App)
- PRを立ててマージ (人間レビューを挟める)
- 別リポジトリ/外部サービスから `workflow_dispatch` で連携
- 手動でファイルを置く (試作期の半手動運用)

逆に「台本なしでも毎日鳴る」ため、サービスが止まっても放送は途切れない(品質は下がる)。

`run_daily.py --script`: `auto`(既定) / `template` / `gemini` / `external` / `none`(publishのみ)

## 台本の形 (episodes/<日付>.json, format: radio/episode-1)

- `opening`/`news[].lines`/`closing` は `{"say","show"}` の並び。`say` は読み上げ用(英字はカタカナ化)、`show` は字幕用
- `news[]` は `label`・`points`・`lines`・`url`(出典、必須)・`link`{url,title,site}
- `lines_timed`(行ごとの秒)と`segments`(パート区切り)は音声を作ったときに `assemble.py` が埋める。手で台本を書いたらこの2つは無くてよい(再生成される)
- `seconds`・`made_at` も assemble が書く

## 声 (station.json voice)

- `engine`: `voicevox` | `kokoro` | `api`
- voicevox: `models/vvm/*.vvm` + `models/open_jtalk_dic_utf_8-1.11` + `models/voicevox_onnxruntime-*/` が必要(workflowが自動DL・キャッシュ)。`style_id` で話者指定
- kokoro: `models/kokoro/{kokoro-v1.0.onnx,voices-v1.0.bin}`、`voice` に `jf_*`/`jm_*`
- api: OpenAI互換 `/v1/audio/speech` を持つ任意のエンドポイント(AivisSpeechエンジン等)
- 声のクレジットは `station.json` の `credits` に必ず書く(VOICEVOX系はライセンス上必須)

## 音声ファイルの扱い

- `audio/` は gitignore。main には絶対コミットしない
- `publish.py` が `keep_days` 日分だけを `dist/` に集め、Actionsが `gh-pages` ブランチへpush
- 外部URLの音声を使う場合は台本に `"audio": "<URL>"` を書く

## やってはいけないこと

- 音声を main にコミットしない
- 他サイトの画像を保存して入れない(リンクカードはURLのみ。OGP画像を足す場合もURL参照に留める)
- 秘密情報(APIキー等)をJSONやコードに書かない。キーはGitHub Secretsへ
- 事実は出典の内容だけ。台本に出典のない話を書かない

## ローカルでの試し方

```bash
cd /home/wakame/work/radio
.venv/bin/python pipeline/collect.py --out /tmp/cand.json
GEMINI_API_KEY=... .venv/bin/python pipeline/script.py --date 2026-11-09 --candidates /tmp/cand.json
.venv/bin/python pipeline/assemble.py --date 2026-11-09
.venv/bin/python pipeline/publish.py
cd dist && python3 -m http.server 8787
```

## BGM

`bgm/morning.mp3` は `tools/make_bgm.py` で生成した簡易パッドループ(自作・自由利用)。
`station.json` の `bgm.enabled=false` または `--no-bgm` で無効化。差し替えはファイルを置き換えるだけ。
