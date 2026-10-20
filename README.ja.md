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
> このプロジェクトは実験段階で、活発に開発中です。コマンドとライブラリの API は予告なく変わることがあり、今後のリリースで形式が増えます。

anypatch は、同じコードの上にあるひとつのライブラリとひとつのコマンドラインです。どの機能も型付きの Python 関数とコマンドの両方で使え、コマンドはその関数を呼ぶだけです。ライブラリは Python 標準ライブラリ以外に何も必要とせず、コマンドラインは Typer を加えます。

## 使い方

```console
$ anypatch make clean.bin hacked.bin -o title.bps
wrote          title.bps, 38 bytes
$ anypatch apply clean.bin title.bps fix.ips -o out.bin
applied        title.bps, fix.ips
wrote          out.bin, 65,536 bytes
$ anypatch apply clean.bin title.bps clash.ups -o never.bin
the patches conflict:
  0x000104..0x000106: title.bps writes 5449, clash.ups writes 5858
$ anypatch merge clean.bin title.bps fix.ips -o both.xdelta
wrote          both.xdelta, 52 bytes
$ anypatch info title.bps
format         BPS
bound by       CRC32 of the source and of the result
size           38 bytes
```

```python
from pathlib import Path

from anypatch import api
from anypatch.patchio import Format

clean = Path("clean.bin").read_bytes()
patches = [api.load(Path(name).read_bytes(), name=name) for name in ("title.bps", "fix.ips")]
Path("out.bin").write_bytes(api.apply(clean, patches).image)
Path("both.xdelta").write_bytes(api.merge(clean, patches, Format.XDELTA)[".xdelta"])
```

## コマンド

| コマンド | ライブラリ、`anypatch.api` 内 | 答えること |
|:--|:--|:--|
| `anypatch make <before> <after> -o <patch>` | `make(before, after, format)` | あるファイルを別のファイルに変えるパッチ。`--format` を指定しない限り、`-o` の拡張子が形式を決めます |
| `anypatch apply <source> <patch>... -o <out>` | `apply(source, patches)` | 衝突の検査のあと、すべてのパッチを当てたソース |
| `anypatch merge <source> <patch>... -o <patch>` | `merge(source, patches, format)` | すべてのパッチと同じことをするひとつのパッチ |
| `anypatch convert <source> <patch> -o <patch>` | `convert(source, patch, format)` | 同じ変更を別の形式で |
| `anypatch info <patch> [--json]` | `identify(data, name=...)` | パッチの形式と、ソースへの紐付け方 |
| `anypatch formats [--json]` | `formats()` | すべての形式と、読み込み・書き出しの可否、拡張子 |
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | このインストールが動くか: バージョン、Python、プラットフォーム、コーデック、各形式の往復 |
| `anypatch --version` | `anypatch.version.VERSION` | インストールされているバージョン |

`apply` と `merge` の `--clean <file>` は、入力にすでにパッチが当たっているときのクリーンなソースを指定します。`--description` は APS、EBP、PPF、RUP のパッチが持つ文字列を設定します。出力はすべて書き込む前に作るため、拒否された場合はファイルが残りません。エラーは標準エラー出力に出し、終了コードは 1 です。

## 形式

| 形式 | 読み込み | 書き出し | 拡張子 | ソースへの紐付け |
|:--|:--|:--|:--|:--|
| IPS | はい | はい | `.ips` | なし。16 MiB を超える変更は IPS32 で書き出します |
| EBP | はい | はい | `.ebp` | なし。`EOF` の後ろに JSON のメタデータを持つ IPS |
| ZPS | はい | はい | `.zps`、`.ip1` | 横に置く `.hdr`。ソースの先頭 64 バイトで、CRC の組で照合します |
| N64 用 APS | はい | はい | `.aps` | ヘッダのカートコード、地域、CRC の組 |
| GBA 用 APS | はい | いいえ | `.aps` | 元のサイズと、64 KiB ブロックごとの CRC16 |
| UPS | はい | はい | `.ups` | 元と結果の CRC32 |
| BPS | はい | はい | `.bps` | 元と結果の CRC32 |
| PPF 1.0、2.0、3.0 | はい | 元に戻すためのデータ付きの 3.0 として | `.ppf` | PPF 2.0 は元のサイズとブロックチェック、PPF 3.0 はブロックチェックと元に戻すためのデータ |
| RUP、NINJA 2.0 | はい | はい | `.rup` | ファイル項目ごとの、元と結果の MD5 |
| PMSR | はい | いいえ | `.mod`、`.pmsr` | Paper Mario USA 1.0。サイズと CRC32 で照合します。そのままでも Yay0 の中でも読めます |
| BDF、bsdiff 4 | はい | はい | `.bdf`、`.bsdiff` | なし |
| xdelta、VCDIFF | はい | はい | `.xdelta`、`.vcdiff`、`.xd3`、`.delta` | パッチが持つ場合、各ウィンドウの Adler-32 チェックサム。xdelta3 の出力を、二次圧縮なし、LZMA、DJW、FGK のいずれでも読み込みます |

形式は中身で判定し、`.zps` か `.ip1` という名前の IPS だけを ZPS として読みます。各パッチはクリーンなソースにそれぞれ単独で当て、変わるバイトを比べます。同じバイトに違う値を書く 2 つのパッチは、すべての範囲と両方の値を示して拒否し、同じ値の書き込みは統合します。ソースのチェックサムを持つ形式のパッチは、ほかのファイルには両方の値を示して拒否し、ソースにすでに結果が入っていれば適用済みと報告します。1 GiB とソースのどちらよりも大きい結果を主張するパッチは、何も確保する前に拒否します。

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
