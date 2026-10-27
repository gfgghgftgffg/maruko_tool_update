# 配置外部工具

Python 依赖与视频编码工具分开安装：`pip install -r requirements.txt` 只安装拖放组件，不会安装 FFmpeg、x265 或 MP4Box。

## 需要哪些程序

| 功能 | 需要 |
|---|---|
| AV1 10bit | FFmpeg（含 libsvtav1）和 ffprobe |
| x265 10bit | FFmpeg、ffprobe、支持 10bit 的独立 x265、GPAC 的 MP4Box |

FFmpeg 的 libx265 不是独立 x265 程序的替代品。8bit-only 的 x265 也不能用于默认的 10bit 压制。AV1 使用所选 FFmpeg 内置的 SVT-AV1，模板中的高级选项需要相应库版本支持。

## 获取程序

### Windows

- FFmpeg / ffprobe：从 [FFmpeg 下载页](https://ffmpeg.org/download.html#build-windows) 选择可信构建，解压后使用 `bin/ffmpeg.exe` 和 `bin/ffprobe.exe`。共享构建的配套 DLL 必须一起保留。
- x265 10bit：使用本项目工具更新包的 `x265_64-10bit[gcc].exe`，或按 [构建指南](BUILD.md) 编译。也可指定其他兼容的 10bit / 多位深 x265 CLI。
- MP4Box：使用已有小丸中的版本，或安装 [GPAC](https://gpac.io/downloads/)。

工具更新包不提供 ffprobe，需另行从 FFmpeg 构建中取得；不要误以为安装 Python 依赖就已安装视频工具。

### macOS

使用匹配本机架构的原生程序，不使用 Windows EXE。Homebrew 用户可安装：

```sh
brew install ffmpeg x265
```

x265 模式还需按 [GPAC 官方说明](https://gpac.io/downloads/) 安装 MP4Box。使用带 Tk 的 Python 3.11+；可运行 `python3 -m tkinter` 检查 Tk 是否可用。

### Linux

Debian / Ubuntu 可先安装：

```sh
sudo apt install python3 python3-venv python3-tk ffmpeg x265
```

x265 模式还需安装提供 `MP4Box` 的 GPAC；具体安装方式取决于发行版，见 [GPAC 官方说明](https://gpac.io/downloads/)。发行版的 FFmpeg / SVT-AV1 版本可能不支持全部模板参数，安装后应运行下方的短片检查。

## 在哪里配置

### 界面

点击主窗口的 **“工具设置”**，选择：

- 工具目录（可选）。
- FFmpeg。
- ffprobe。
- x265 10bit。
- MP4Box。

点击“检查工具”可查看当前勾选编码器解析到的真实路径和版本，点击“保存”写入本地 `config.json`。留空的项目自动查找，不修改编码参数。

### 配置文件

`config.example.json` 是仓库模板；`config.json` 是本机配置，不入库。界面首次保存时自动创建本机配置。

以下仅展示工具字段，手工编辑时合并到现有配置，**不要覆盖 `profiles.*.params`**：

```json
{
  "tools_dir": "tools",
  "ffmpeg": "tools/ffmpeg",
  "ffprobe": "tools/ffprobe",
  "mp4box": "tools/MP4Box",
  "profiles": {
    "x265": {
      "path": "tools/x265"
    }
  }
}
```

Windows 对应文件名可以是 `ffmpeg.exe`、`ffprobe.exe`、`MP4Box.exe`、`x265_64-10bit[gcc].exe`。绝对路径、`~` 和环境变量也可使用；配置中的相对路径以项目根目录为基准，不受启动时工作目录影响。

查找顺序为：命令行覆盖 → 指定程序路径 → `tools_dir` → 项目内 `tools/` → `dist/overlay/tools/` → `vendor/ffmpeg/bin/` → PATH。ffprobe 还会优先在选定的 FFmpeg 同目录查找。无效路径可能回退，因此以检查结果显示的实际路径为准。

工具可以放在项目外的任意目录，配置绝对路径即可。可选的项目内 `tools/` 不入库；本项目不会自动下载安装或替换系统工具。

## 检查依赖

在项目根目录，用安装界面依赖的同一个 Python 执行：

```sh
# 路径、启动与 FFmpeg 的 libsvtav1 检查
python check_tools.py

# 只使用 AV1，无需 x265 / MP4Box
python check_tools.py --encoder svt-av1

# 按当前参数编码短测试片，检查参数兼容性和真实输出位深
python check_tools.py --smoke
```

检查会打印实际使用的可执行文件路径和版本。`--smoke` 只在系统临时目录创建合成短片，不修改 CRF、画质参数、个人配置或输入视频。全部通过返回退出码 0，失败返回非零。

## Python 启动器

macOS / Linux 启动器依次使用 `MARUKO_PYTHON`、已激活的虚拟环境 / Conda 环境、项目 `.venv/bin/python`，最后尝试 PATH 中的 `python3` / `python`。Windows 同样支持显式设置、已激活环境和项目 `.venv`，并兼容本机已有 codex 环境。

例如：

```sh
MARUKO_PYTHON=/path/to/python3 sh start_gui.sh
```

所有平台都可以直接使用 `python gui.py` 和 `python encode.py`，不依赖某个固定环境名称。
