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

anypatch 是建立在同一份代码之上的一个库和一个命令行。每项功能都既是一个带类型的 Python 函数，也是一条命令，而命令只调用该函数。库除 Python 标准库外不需要任何东西；命令行另外使用 Typer。

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

## 命令

| 命令 | 库，位于 `anypatch.api` | 回答的问题 |
|:--|:--|:--|
| `anypatch make <before> <after> -o <patch>` | `make(before, after, format)` | 把一个文件变成另一个文件的补丁。除非用 `--format` 指定，否则由 `-o` 的扩展名决定格式 |
| `anypatch apply <source> <patch>... -o <out>` | `apply(source, patches)` | 经过冲突检查后，应用了所有补丁的源文件 |
| `anypatch merge <source> <patch>... -o <patch>` | `merge(source, patches, format)` | 一个效果等于所有补丁之和的补丁 |
| `anypatch convert <source> <patch> -o <patch>` | `convert(source, patch, format)` | 以另一种格式表达的同一改动 |
| `anypatch info <patch> [--json]` | `identify(data, name=...)` | 补丁是什么格式，以及什么把它绑定到源文件 |
| `anypatch formats [--json]` | `formats()` | 每种格式、能否读取和写出，以及扩展名 |
| `anypatch doctor [--json]` | `anypatch.doctor.diagnose()` | 这次安装能否工作：版本、Python、平台、编解码器，以及每种格式的往返检查 |
| `anypatch --version` | `anypatch.version.VERSION` | 已安装的版本 |

`apply` 和 `merge` 的 `--clean <file>` 在输入已带有补丁时指定干净的源文件。`--description` 设置 APS、BPS、EBP、PPF 或 RUP 补丁携带的文字。所有输出都在写入任何内容之前生成，所以拒绝时不会留下文件。错误写到标准错误，退出码为 1。

## 格式

| 格式 | 读取 | 写出 | 扩展名 | 绑定到源文件的方式 |
|:--|:--|:--|:--|:--|
| IPS | 是 | 是 | `.ips` | 无。超过 16 MiB 的改动写成 IPS32 |
| EBP | 是 | 是 | `.ebp` | 无。在 `EOF` 之后带 JSON 元数据的 IPS |
| ZPS | 是 | 是 | `.zps`、`.ip1` | 旁边的 `.hdr`，即源文件的前 64 字节，按 CRC 对比较 |
| N64 用 APS | 是，原生或字节交换顺序 | 原生顺序 | `.aps` | 源文件是 N64 ROM 时为卡带代码、地区和 CRC 对；否则与 RomPatcher.js 一样，写入不含这些字段的文件头 |
| GBA 用 APS | 是 | 是，用 `--format aps-gba` | `.aps` | 源文件大小，以及每个 64 KiB 块的 CRC16。较短的最后一块无论是否补零都能读取。只有大小不变且较短的最后一块未被修改时，RomPatcher.js 才能读取 |
| UPS | 是 | 是 | `.ups` | 源文件和结果的 CRC32 |
| BPS | 是 | 是 | `.bps` | 源文件和结果的 CRC32 |
| PPF 1.0、2.0、3.0 | 是 | 写成带撤销数据的 3.0 | `.ppf` | PPF 2.0 的源文件大小和块校验；PPF 3.0 的块校验和撤销数据 |
| RUP，NINJA 2.0 | 是 | 是 | `.rup` | 每个文件条目的源文件和结果的 MD5，按条目的 ROM 类型先做与 NINJA 相同的转换再计算：去掉文件头，还原排列 |
| PMSR | 是 | 是，用 `--format pmsr` | `.mod`、`.pmsr` | Paper Mario USA 1.0，按大小和 CRC32；读取时原样或在 Yay0 之中均可，写出为原样 |
| BDF，bsdiff 4 | 是 | 是 | `.bdf`、`.bsdiff` | 无 |
| BSDIFF43，ENDSLEY | 是 | 是，用 `--format bsdiff43` | `.bsdiff` | 无 |
| GDIFF | 是 | 是 | `.gdiff`、`.gdf` | 无 |
| xdelta，VCDIFF | 是 | 是 | `.xdelta`、`.vcdiff`、`.xd3`、`.delta` | 补丁带有时，每个窗口的 Adler-32 校验和。读取 xdelta3 的输出，无论无二次压缩、LZMA、DJW 还是 FGK |

格式由内容决定；只有名为 `.zps` 或 `.ip1` 的 IPS 才按 ZPS 读取。每个补丁都单独应用到干净的源文件上，再比较各自改变的字节。向同一字节写入不同值的两个补丁会被拒绝，并列出每个范围和双方的值；相同的写入会合并。格式带有源文件校验和的补丁，用在其他文件上时会被拒绝并给出双方的值；源文件已经包含结果时，会报告为已应用。声称结果大于 1 GiB 且大于源文件的补丁，会在分配任何内存之前被拒绝。

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
| 与参考工具交换边界文件 | `PYTHONPATH=src python scripts/interop.py --tool xdelta3 --work <dir>` |
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
