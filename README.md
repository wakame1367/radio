# radio (仮)

毎朝のニュースを「ラジオ番組」として自動生成・配信する個人放送局。
[monoradio102/myradio](https://github.com/monoradio102/myradio) の設計を参考にした自前実装。

## 構成

```
pipeline/    毎朝の生成パイプライン (Python)
  collect.py   RSS/トレンド/Web検索 → ニュース候補
  script.py    Gemini API → 台本JSON (episodes/YYYY-MM-DD.json)
  voice.py     TTS (voicevox_core / Kokoro / AivisSpeech) 行別合成
  assemble.py  連結 + lines_timed 生成 + BGMダッキング → mp3
  publish.py   episodes.json 更新 → gh-pages へ公開
site/        GitHub Pages で配信する Web プレーヤー (vanilla JS)
episodes/    台本JSON (永続)
audio/       生成音声 mp3 (gitignore、公開は gh-pages 側のみ)
audition/    声の試聴サンプル + 試聴ページ
.github/     毎朝の自動実行ワークフロー
station.json 局の設定
episodes.json 回の一覧
```

## 運用

- GitHub Actions が毎朝 JST で収集→台本→音声→公開まで自動実行
- 公開は `gh-pages` ブランチ経由の GitHub Pages
- 音声は main にはコミットしない (直近 N 日分のみ配信)

## 開発メモ

- LLM: Gemini API (無料枠) — Secret `GEMINI_API_KEY`
- TTS: ユーザーが試聴して選択 (audition/ 参照)
- 依存は pip のみ (ffmpeg 非依存: lameenc + miniaudio + numpy)
