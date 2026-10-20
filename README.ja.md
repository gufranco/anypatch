<div align="center">

<h1>anypatch</h1>

<strong>公開仕様のあるすべての形式で、バイナリパッチを読み、書き、統合し、変換します</strong>

<br>
<br>

[English](README.md) | 日本語 | [简体中文](README.zh-Hans.md) | [繁體中文 (香港)](README.zh-HK.md)

<br>

[![CI](https://github.com/gufranco/anypatch/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/anypatch/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](pyproject.toml)
[![Types](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

> [!WARNING]
> このプロジェクトは実験段階で、活発に開発中です。パッチ形式は [n64-save-patches](https://github.com/gufranco/n64-save-patches-python) から移行中で、今後のリリースで順に加わります。コマンドとライブラリの API は予告なく変わることがあります。

anypatch は、同じコードの上にあるひとつのライブラリとひとつのコマンドラインです。どの機能も型付きの Python 関数とコマンドの両方で使え、コマンドはその関数を呼ぶだけです。ライブラリは Python 標準ライブラリ以外に何も必要とせず、コマンドラインは Typer を加えます。

## 使い方

```console
$ anypatch doctor
anypatch     0.1.0
python       3.14.0
platform     Darwin arm64
zlib         available
bz2          available
lzma         available
```

```python
from anypatch import doctor

report = doctor.diagnose()
print(report.healthy)
```

`doctor` は、失敗したチェックがなければ 0、ひとつでもあれば 1 で終了します。実行中の Python にないコーデックは `missing` と表示され、それを使う形式は読み込まれません。それだけではインストールは失敗扱いになりません。`anypatch doctor --json` は同じ結果を `healthy` と `checks` を持つ JSON で出力します。

## コマンド

| コマンド | ライブラリ | 答えること |
|:--|:--|:--|
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | このインストールが動くか: バージョン、Python、プラットフォーム、各形式が使う標準ライブラリのコーデック |
| `anypatch --version` | `anypatch.version.VERSION` | インストールされているバージョン |

## インストール

### Homebrew

```bash
brew tap gufranco/anypatch https://github.com/gufranco/anypatch
brew install gufranco/anypatch/anypatch
anypatch doctor
```

リポジトリ名が `homebrew-anypatch` ではないため、tap には URL が必要です。`brew install --HEAD gufranco/anypatch/anypatch` は最新リリースの代わりに `main` の先端をビルドします。

### 別のプロジェクトの依存として

anypatch は PyPI に公開していません。リリースタグに依存してください:

```toml
dependencies = ["anypatch @ git+https://github.com/gufranco/anypatch@v0.1.0"]
```

そのプロジェクトがコマンドも必要とする場合だけ、`anypatch[cli] @ git+...` のように `cli` エクストラを付けます。付けない場合、コマンドラインの `anypatch` は入手方法を表示して 1 で終了します。

### ソースから

| ツール | バージョン |
|:--|:--|
| Python | 3.11 以降 |
| uv | 最近のもの |

```bash
git clone https://github.com/gufranco/anypatch.git
cd anypatch
uv sync
uv run anypatch doctor
```

`uv run python -m anypatch` でも同じコマンドラインが動きます。

## 開発

| ゲート | コマンド |
|:--|:--|
| テスト、ステートメントとブランチ 100% のゲート付き | `uv run pytest --cov` |
| リント | `uv run ruff check .` |
| フォーマット | `uv run ruff format --check .` |
| 型、strict | `uv run mypy` |
| JSON と YAML のフォーマット | `pnpm run format:check` |

`git config core.hooksPath .githooks` で、各コミットの前にコミットメッセージの検査と速いゲートが走ります。コミットは [Conventional Commits](https://www.conventionalcommits.org/) に従います。semantic-release がそれを読んで各リリースを作り、バージョンが 0.x の間は破壊的変更でマイナー番号が上がります。

## サポート

| 用件 | 場所 |
|:--|:--|
| バグ報告 | [GitHub Issues](https://github.com/gufranco/anypatch/issues) |
| セキュリティ報告 | [セキュリティポリシー](SECURITY.md) |
| 貢献 | [貢献ガイド](CONTRIBUTING.md) |
| 行動規範 | [行動規範](CODE_OF_CONDUCT.md) |

## ライセンス

[MIT](LICENSE)。各形式は [NOTICE.md](NOTICE.md) にある仕様とオープンな実装から学びました。
