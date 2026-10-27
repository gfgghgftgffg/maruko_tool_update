# maruko_tool_update

为小丸工具箱构建命令行工具，并提供独立的 **x265 / AV1 视频压制界面**。

| 用途 | 入口 | 平台 |
|---|---|---|
| 拖放视频、批量压制、保存参数、查看进度 | Windows：`start_gui.cmd`；macOS：`start_gui.command`；Linux：`sh start_gui.sh` | Windows 已实测，macOS / Linux 待实机验收 |
| 命令行压制 | `python encode.py` | Python 3.11+，需相应外部工具 |
| 构建、验证小丸工具更新包 | `python scripts/project.py` | Windows x64 |

## 开始压制

安装 Python 3.11+（带 Tk），克隆项目：

```sh
git clone https://github.com/gfgghgftgffg/maruko_tool_update.git
cd maruko_tool_update
```

Windows：

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\start_gui.cmd
```

macOS / Linux：

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
sh start_gui.sh
```

macOS 也可双击 `start_gui.command`。从 ZIP 下载后若脚本无执行权限，先运行 `chmod +x start_gui.command`。Linux 需安装 Tk 支持（通常为 `python3-tk`）；macOS 使用带 Tk 的 Python。

启动器会自动使用项目 `.venv`。也可激活自己的 Python / Conda 环境，或用 `MARUKO_PYTHON` 指定解释器。

1. 第一行拖入一个或多个视频，第二行拖入批量文件夹；两行输入合并去重，可单独清空。
2. 第三行选择输出目录，留空则写入源视频旁的 `encoded/`。
3. 勾选 x265 或 AV1，并编辑各自的参数。两者都勾选时分别输出一份。
4. 点击“开始压制”。界面显示 `4/n 个视频` 和当前编码的进度，支持取消。

参数、路径和勾选状态自动保存到本地 `config.json`。没有本地配置时读取 [config.example.json](config.example.json)，首次保存后生成本地配置。

> [!IMPORTANT]
> 默认使用 **10bit**：AV1 CRF 为 **28**，x265 CRF 为 **23**；程序不会为了缩小体积自动修改 CRF 或画质参数。CRF 不保证输出比源文件小，体积增大时只给出提示。

已有输出默认跳过，源视频不会被覆盖。重新压制请选新的输出目录。AV1 使用闭合 GOP，并检查输出文件能否从中段随机访问。

完整操作、参数格式、音频与容器选项见 [压制使用说明](docs/ENCODING.md)。

### 安装与配置视频工具

`requirements.txt` **只安装 Python 拖放组件，不包含编码程序**：

- AV1 10bit：FFmpeg（含 `libsvtav1`）与 ffprobe。
- x265 10bit：再加支持 10bit 的独立 x265 和 GPAC 的 MP4Box。

在界面点击 **“工具设置”**，为 FFmpeg、ffprobe、x265 10bit 和 MP4Box 选择路径并保存；也可将原生程序加入 PATH，留空自动查找。Windows EXE 不能用于 macOS / Linux。

工具路径保存在本地 `config.json` 的 `ffmpeg`、`ffprobe`、`mp4box`、`profiles.x265.path` 字段。`tools_dir` 可指定统一目录。相对路径以项目根目录为基准，个人配置不入库。

安装后，在所用 Python 环境运行检查（只使用 AV1 时加 `--encoder svt-av1`）：

```powershell
# Windows
.\.venv\Scripts\python check_tools.py --smoke
```

```sh
# macOS / Linux
.venv/bin/python check_tools.py --smoke
```

检查会打印实际路径和版本，并用当前参数编码短片、检查 10bit 输出。各平台的工具安装方法、配置示例和查找顺序见 [外部工具配置](docs/TOOLS.md)。

实验资料和个人任务记录不属于项目目录；视频、配置备份不入库或打包。标准的 `build/`、`vendor/`、`dist/` 仅用于本地构建和测试，均被 Git 忽略。

### 命令行

```sh
python encode.py "视频.mp4" --encoder svt-av1 --output-dir "压制结果"
python encode.py "视频目录" --encoder x265 --recursive
python encode.py "视频.mp4" --dry-run
python encode.py --help
```

Windows 可将文件或文件夹拖到 `encode.cmd`，按已保存的默认编码器直接压制；macOS / Linux 可运行 `sh encode.sh "视频.mp4"`。这些入口不带参数时打开界面。

## 小丸工具更新包

构建流程用于更新小丸调用的 Windows x64 工具：

| 工具 | 锁定版本 / 产物 |
|---|---|
| x264 | `t_mod_New` 0.165.3223+83M，8bit |
| x265 | 官方 4.2+37-b81f650e2，8bit / 10bit |
| FFmpeg | 9.0.2 shared，EXE 与七个配套 DLL |

独立压制界面只提供 x265、AV1；x264 仅用于小丸工具构建。AV1 调用 FFmpeg 内置的 libsvtav1，本项目不另行编译 SVT-AV1。

安装更新包时退出小丸、备份原文件，再将包内 `tools/` 的全部文件复制到小丸对应目录。不要混用不同包的 EXE 和 DLL。具体清单与安装说明见 [更新包说明](packaging/README.md)。

```sh
python scripts/project.py doctor
python scripts/project.py prepare
python scripts/project.py build --encoder all --bit-depth 8
python scripts/project.py verify --bit-depth 8 --toolbox "小丸安装目录"
python scripts/project.py package --bit-depth 8
```

依赖锁定见 [dependencies.lock.json](dependencies.lock.json)；环境要求和构建步骤见 [构建指南](docs/BUILD.md)，后续维护见 [维护流程](docs/MAINTENANCE.md)。

`package` 只生成小丸工具覆盖包，不包含独立压制界面，也不会自动发布。独立界面请从源码运行，现有 release ZIP 不包含该界面。

## 验证与限制

```sh
python -m unittest test_encode test_gui test_tools -v
```

压制测试覆盖 x265 / AV1 的 8/10bit、音轨复制、批量、中文路径、进度、参数持久化、取消和快进解码。需要已安装外部工具；GUI 测试还需要桌面会话。产物写入 `build/`。

小丸工具覆盖包与独立压制界面分别验收，测试结果不互相通用。已测范围见 [兼容性说明](docs/COMPATIBILITY.md)。

当前压制面向普通 SDR、恒定帧率视频，不自动保留字幕、附件、章节和多音轨；PQ/HLG HDR 会拒绝处理。

## 目录

```text
gui.py / encode.py          独立界面与编码核心
check_tools.py             外部工具路径、版本、短片与位深检查
start_gui.cmd / encode.cmd   Windows 启动入口
start_gui.command           macOS 双击入口
start_gui.sh / encode.sh     macOS / Linux 启动入口
config.example.json        可入库的默认配置模板
config.json                本机参数与路径，不入库
test_encode.py / test_gui.py / test_tools.py  压制、界面和启动器测试
scripts/                   构建、验证、打包和 Python 启动器
patches/                   小丸工具兼容性补丁
packaging/                 工具覆盖包的安装说明
docs/                      压制、构建、兼容性和维护文档
vendor/ / build/ / dist/    依赖、测试产物和工具更新包，不入库
```

上游来源及分发注意事项见 [第三方组件](docs/THIRD_PARTY.md)。
