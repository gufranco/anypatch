<div align="center">

<h1>anypatch</h1>

<strong>以每一種有公開規格的格式讀取、寫入、合併和轉換二進位修補檔</strong>

<br>
<br>

[English](README.md) | [日本語](README.ja.md) | [简体中文](README.zh-Hans.md) | 繁體中文 (香港)

<br>

[![CI](https://github.com/gufranco/anypatch/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/anypatch/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](pyproject.toml)
[![Types](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

anypatch 是建立在同一份程式碼之上的一個程式庫和一個命令列。每項功能既是一個附型別的 Python 函式，亦是一條指令，而指令只會呼叫該函式。程式庫除 Python 標準程式庫外不需要任何東西；命令列另外使用 Typer。

## 用法

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

## 指令

| 指令 | 程式庫，位於 `anypatch.api` | 回答的問題 |
|:--|:--|:--|
| `anypatch make <before> <after> -o <patch>` | `make(before, after, format)` | 把一個檔案變成另一個檔案的修補檔。除非以 `--format` 指定，否則由 `-o` 的副檔名決定格式 |
| `anypatch apply <source> <patch>... -o <out>` | `apply(source, patches)` | 經衝突檢查後，套用了所有修補檔的來源檔案 |
| `anypatch merge <source> <patch>... -o <patch>` | `merge(source, patches, format)` | 一個效果等於所有修補檔之和的修補檔 |
| `anypatch convert <source> <patch> -o <patch>` | `convert(source, patch, format)` | 以另一種格式表達的同一改動 |
| `anypatch info <patch> [--json]` | `identify(data, name=...)` | 修補檔是甚麼格式，以及甚麼把它綁定到來源 |
| `anypatch formats [--json]` | `formats()` | 每種格式、能否讀取和寫出，以及副檔名 |
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | 這次安裝能否運作：版本、Python、平台、編解碼器，以及每種格式的往返檢查 |
| `anypatch --version` | `anypatch.version.VERSION` | 已安裝的版本 |

`apply` 和 `merge` 的 `--clean <file>` 在輸入已帶有修補時指定乾淨的來源。`--description` 設定 APS、BPS、EBP、PPF 或 RUP 修補檔攜帶的文字。所有輸出都在寫入任何內容之前產生，所以拒絕時不會留下檔案。錯誤寫到標準錯誤，結束碼為 1。

## 格式

| 格式 | 讀取 | 寫出 | 副檔名 | 綁定來源的方式 |
|:--|:--|:--|:--|:--|
| IPS | 是 | 是 | `.ips` | 沒有。超過 16 MiB 的改動寫成 IPS32 |
| EBP | 是 | 是 | `.ebp` | 沒有。在 `EOF` 之後附 JSON 中繼資料的 IPS |
| ZPS | 是 | 是 | `.zps`、`.ip1` | 旁邊的 `.hdr`，即來源的首 64 個位元組，按 CRC 組合比對 |
| N64 用 APS | 是，原生或位元組交換次序 | 原生次序 | `.aps` | 來源是 N64 ROM 時為卡帶代碼、地區和 CRC 組合；否則與 RomPatcher.js 一樣，寫入不含這些欄位的檔頭 |
| GBA 用 APS | 是 | 是，用 `--format aps-gba` | `.aps` | 來源大小，以及每個 64 KiB 區塊的 CRC16。較短的最後區塊無論有沒有補零都能讀取。只有大小不變且較短的最後區塊未被修改時，RomPatcher.js 才能讀取 |
| UPS | 是 | 是 | `.ups` | 來源和結果的 CRC32 |
| BPS | 是 | 是 | `.bps` | 來源和結果的 CRC32 |
| PPF 1.0、2.0、3.0 | 是 | 寫成附還原資料的 3.0 | `.ppf` | PPF 2.0 的來源大小和區塊檢查；PPF 3.0 的區塊檢查和還原資料 |
| RUP，NINJA 2.0 | 是 | 是 | `.rup` | 每個檔案項目的來源和結果的 MD5 |
| PMSR | 是 | 是，用 `--format pmsr` | `.mod`、`.pmsr` | Paper Mario USA 1.0，按大小和 CRC32；讀取時原樣或在 Yay0 之內皆可，寫出為原樣 |
| BDF，bsdiff 4 | 是 | 是 | `.bdf`、`.bsdiff` | 沒有 |
| GDIFF | 是 | 是 | `.gdiff`、`.gdf` | 沒有 |
| xdelta，VCDIFF | 是 | 是 | `.xdelta`、`.vcdiff`、`.xd3`、`.delta` | 修補檔附有時，每個視窗的 Adler-32 校驗和。讀取 xdelta3 的輸出，不論沒有二次壓縮、LZMA、DJW 或 FGK |

格式由內容決定；只有名為 `.zps` 或 `.ip1` 的 IPS 才按 ZPS 讀取。每個修補檔都單獨套用到乾淨的來源上，再比較各自改變的位元組。向同一位元組寫入不同值的兩個修補檔會被拒絕，並列出每個範圍和雙方的值；相同的寫入會合併。格式附有來源校驗和的修補檔，用在其他檔案上時會被拒絕並列出雙方的值；來源已經包含結果時，會報告為已套用。聲稱結果大於 1 GiB 且大於來源的修補檔，會在配置任何記憶體之前被拒絕。

## 安裝

### Homebrew

```bash
brew tap gufranco/anypatch https://github.com/gufranco/anypatch
brew install gufranco/anypatch/anypatch
anypatch doctor
```

儲存庫名稱不是 `homebrew-anypatch`，所以 tap 需要提供 URL。`brew install --HEAD gufranco/anypatch/anypatch` 會建置 `main` 的最新提交，而不是最新發佈版本。

### 作為另一個專案的依賴

anypatch 不會發佈到 PyPI。請依賴一個發佈標籤：

```toml
dependencies = ["anypatch @ git+https://github.com/gufranco/anypatch@v0.1.0"]
```

只有當該專案亦需要指令時，才加上 `cli` 附加項，寫成 `anypatch[cli] @ git+...`。不加的話，命令列中的 `anypatch` 會說明如何取得它，並以 1 結束。

### 從原始碼

| 工具 | 版本 |
|:--|:--|
| Python | 3.11 或更新 |
| uv | 任何較新版本 |

```bash
git clone https://github.com/gufranco/anypatch.git
cd anypatch
uv sync
uv run anypatch doctor
```

`uv run python -m anypatch` 會執行同一個命令列。

## 開發

| 檢查 | 指令 |
|:--|:--|
| 測試，附語句和分支 100% 的門檻 | `uv run pytest --cov` |
| 與參考工具交換邊界檔案 | `PYTHONPATH=src python scripts/interop.py --tool xdelta3 --work <dir>` |
| 程式碼檢查 | `uv run ruff check .` |
| 格式 | `uv run ruff format --check .` |
| 型別，strict | `uv run mypy` |
| JSON 和 YAML 格式 | `pnpm run format:check` |

`git config core.hooksPath .githooks` 會在每次提交前執行提交訊息檢查和快速檢查。提交遵循 [Conventional Commits](https://www.conventionalcommits.org/)；semantic-release 讀取它們來發佈每個版本，版本為 0.x 期間，破壞性變更會提升次版本號。

## 支援

| 需要 | 位置 |
|:--|:--|
| 報告錯誤 | [GitHub Issues](https://github.com/gufranco/anypatch/issues) |
| 報告保安問題 | [保安政策](SECURITY.md) |
| 參與貢獻 | [貢獻指南](CONTRIBUTING.md) |
| 行為守則 | [行為守則](CODE_OF_CONDUCT.md) |

## 授權

[MIT](LICENSE)。各格式是從 [NOTICE.md](NOTICE.md) 列出的規格和開源實作中學到的。
