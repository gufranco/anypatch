<div align="center">

<h1>anypatch</h1>

<strong>以每一种有公开规范的格式读取、写入、合并和转换二进制补丁</strong>

<br>
<br>

[English](README.md) | [日本語](README.ja.md) | 简体中文 | [繁體中文 (香港)](README.zh-HK.md)

<br>

[![CI](https://github.com/gufranco/anypatch/actions/workflows/ci.yml/badge.svg)](https://github.com/gufranco/anypatch/actions/workflows/ci.yml)
[![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)](pyproject.toml)
[![Types](https://img.shields.io/badge/mypy-strict-blue)](pyproject.toml)
[![License](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

</div>

---

> [!WARNING]
> 本项目处于实验阶段，正在积极开发。补丁格式正从 [n64-save-patches](https://github.com/gufranco/n64-save-patches-python) 迁移过来，将在接下来的版本中陆续加入。命令和库 API 可能不经通知就改变。

anypatch 是建立在同一份代码之上的一个库和一个命令行。每项功能都既是一个带类型的 Python 函数，也是一条命令，而命令只调用该函数。库除 Python 标准库外不需要任何东西；命令行另外使用 Typer。

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

没有检查失败时 `doctor` 以 0 退出，有一项失败时以 1 退出。正在运行的 Python 缺少的编解码器会显示为 `missing`，依赖它的格式不会被读取；仅此一点不会让安装判定为失败。`anypatch doctor --json` 以带 `healthy` 和 `checks` 的 JSON 输出同样的报告。

## 命令

| 命令 | 库 | 回答的问题 |
|:--|:--|:--|
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | 这次安装能否工作：版本、Python、平台，以及各格式使用的标准库编解码器 |
| `anypatch --version` | `anypatch.version.VERSION` | 已安装的版本 |

## 安装

### Homebrew

```bash
brew tap gufranco/anypatch https://github.com/gufranco/anypatch
brew install gufranco/anypatch/anypatch
anypatch doctor
```

仓库名不是 `homebrew-anypatch`，所以 tap 需要给出 URL。`brew install --HEAD gufranco/anypatch/anypatch` 构建 `main` 的最新提交，而不是最新发布版。

### 作为另一个项目的依赖

anypatch 不发布到 PyPI。请依赖一个发布标签：

```toml
dependencies = ["anypatch @ git+https://github.com/gufranco/anypatch@v0.1.0"]
```

只有当那个项目也需要命令时，才加上 `cli` 附加项，写成 `anypatch[cli] @ git+...`。不加时，命令行中的 `anypatch` 会说明如何获取它并以 1 退出。

### 从源码

| 工具 | 版本 |
|:--|:--|
| Python | 3.11 或更新 |
| uv | 任一较新版本 |

```bash
git clone https://github.com/gufranco/anypatch.git
cd anypatch
uv sync
uv run anypatch doctor
```

`uv run python -m anypatch` 运行同一个命令行。

## 开发

| 检查 | 命令 |
|:--|:--|
| 测试，带语句和分支 100% 的门槛 | `uv run pytest --cov` |
| 代码检查 | `uv run ruff check .` |
| 格式 | `uv run ruff format --check .` |
| 类型，strict | `uv run mypy` |
| JSON 和 YAML 格式 | `pnpm run format:check` |

`git config core.hooksPath .githooks` 会在每次提交前运行提交信息检查和快速检查。提交遵循 [Conventional Commits](https://www.conventionalcommits.org/)；semantic-release 读取它们来发布每个版本，版本为 0.x 期间，破坏性变更提升次版本号。

## 支持

| 需要 | 位置 |
|:--|:--|
| 报告缺陷 | [GitHub Issues](https://github.com/gufranco/anypatch/issues) |
| 报告安全问题 | [安全策略](SECURITY.md) |
| 参与贡献 | [贡献指南](CONTRIBUTING.md) |
| 行为准则 | [行为准则](CODE_OF_CONDUCT.md) |

## 许可

[MIT](LICENSE)。各格式是从 [NOTICE.md](NOTICE.md) 列出的规范和开源实现中学到的。
