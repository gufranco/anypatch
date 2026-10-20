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

> [!WARNING]
> 本專案處於實驗階段，正積極開發。修補檔格式正由 [n64-save-patches](https://github.com/gufranco/n64-save-patches-python) 遷移過來，會在接下來的版本中陸續加入。指令和程式庫 API 可能不經通知而改變。

anypatch 是建立在同一份程式碼之上的一個程式庫和一個命令列。每項功能既是一個附型別的 Python 函式，亦是一條指令，而指令只會呼叫該函式。程式庫除 Python 標準程式庫外不需要任何東西；命令列另外使用 Typer。

## 用法

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

沒有檢查失敗時 `doctor` 以 0 結束，有一項失敗時以 1 結束。正在執行的 Python 缺少的編解碼器會顯示為 `missing`，依賴它的格式不會被讀取；單憑這一點不會令安裝判定為失敗。`anypatch doctor --json` 以附 `healthy` 和 `checks` 的 JSON 輸出同一份報告。

## 指令

| 指令 | 程式庫 | 回答的問題 |
|:--|:--|:--|
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | 這次安裝能否運作：版本、Python、平台，以及各格式使用的標準程式庫編解碼器 |
| `anypatch --version` | `anypatch.version.VERSION` | 已安裝的版本 |

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
