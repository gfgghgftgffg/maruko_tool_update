# maruko_tool_update

为小丸工具箱构建和维护更新的编码工具，让用户继续使用原有界面和压制参数。更新包采用小丸原文件名和目录结构，可直接复制到安装目录。

项目通过锁定上游版本、保留兼容性补丁和执行验证，为后续工具更新提供可重复的构建流程。

## 当前支持

| 组件 | 状态 |
|---|---|
| Windows x64 / x264 8bit | 已构建并通过命令行兼容性验证 |
| Windows x64 / x265 8bit | 已构建，使用小丸原参数和 FFmpeg 管道调用 |
| Windows x64 / x265 10bit | 已构建并验证 Main 10 输出 |
| Windows x64 / FFmpeg 9.0.2 | 提供独立 ffmpeg.exe 及运行依赖 |

x264 基于 `t_mod_New` 分支，保留额外 AQ、视觉优化、字幕和滤镜扩展，使用 FFmpeg 9.0.2 库读取视频和进行缩放。x265 基于官方源码 `4.2+37-b81f650e2`，由小丸调用 FFmpeg 生成 Y4M 数据后通过管道编码为 HEVC。10bit 版使用同一份源码以 `HIGH_BIT_DEPTH` 编译，输出 Main 10，可直接在小丸的程序选择框中选中。

## 安装更新包

1. 在 [Releases](https://github.com/gfgghgftgffg/maruko_tool_update/releases) 页面下载更新包并解压。
2. 退出小丸工具箱，备份将被覆盖的原文件。
3. 将包内 `tools/` 的全部文件复制到小丸安装目录的 `tools/`，覆盖同名文件。
4. 启动小丸，选择对应编码器。

覆盖清单：

| 文件 | 作用 |
|---|---|
| `x264_64-8bit.exe` | 替换 64 位 8bit 编码器 |
| `x265_64-8bit[gcc].exe` | 替换小丸原 64 位 8bit x265 编码器 |
| `x265_64-10bit[gcc].exe` | 新增 64 位 10bit x265 编码器，可在程序选择框中直接选中 |
| `ffmpeg.exe` | 替换小丸调用的 FFmpeg，用于音频处理及其他 FFmpeg 任务 |
| `avcodec-63.dll` | 解码库 |
| `avdevice-63.dll` | FFmpeg 设备输入输出库 |
| `avfilter-12.dll` | FFmpeg 音视频滤镜库 |
| `avformat-63.dll` | 容器读取库 |
| `avutil-61.dll` | 公共运行库 |
| `swresample-7.dll` | FFmpeg 库的间接依赖 |
| `swscale-10.dll` | 缩放和像素格式转换 |

十一个文件一同复制到 `tools/`。x264 字幕使用小丸原 `VSFilter64.dll`；x265 的解码、缩放和字幕由包内 FFmpeg 处理，最终合并使用原 `MP4Box.exe`。安装后在小丸中选择对应编码器即可沿用原参数。

未来依赖升级可能改变 DLL 名称；以当次 manifest 和 README 为准，不混用不同包的 EXE、DLL。恢复时还原备份的 x264 和 ffmpeg.exe，不盲目删除其他工具可能使用的 DLL。

## 从源码构建

### 环境要求

- Windows x64。
- Python 3.11 或更高版本，管理脚本仅使用标准库。
- Git for Windows，包含 Git Bash。
- MinGW-w64 x64 工具链，包含 GCC 和 `mingw32-make`。
- NASM。
- CMake、Ninja，用于构建 x265。
- 支持 7z 格式的 `tar`。

已验证工具链：GCC 14.2.0、NASM 2.16.01、CMake 3.30.4、Ninja 1.12.1。源码和 FFmpeg 开发包的版本、下载地址及校验值记录在 [dependencies.lock.json](dependencies.lock.json)。

脚本默认从 PATH 和 Git 安装目录查找工具。需要手动指定时，设置以下环境变量：

| 环境变量 | 内容 |
|---|---|
| `MARUKO_BASH` | Git Bash 的 `bash.exe` 路径 |
| `MARUKO_TOOLCHAIN` | MinGW-w64 的 `bin` 目录 |
| `MARUKO_BUILD_CACHE` | 可选的 ASCII 路径构建缓存，用于含非 ASCII 路径的 x265 源码 |

NASM 对部分非 ASCII 路径存在编码问题。源码路径包含非 ASCII 字符时，脚本自动在 Windows Public 目录中创建 ASCII 路径缓存和源码目录联接，也可通过 `MARUKO_BUILD_CACHE` 指定位置。

### 构建步骤

在项目根目录运行：

```powershell
python scripts/project.py doctor
python scripts/project.py prepare
python scripts/project.py build --encoder all --bit-depth 8
python scripts/project.py verify --bit-depth 8 --toolbox "<小丸安装目录>"
python scripts/project.py package --bit-depth 8
```

将 `<小丸安装目录>` 替换为实际路径。验证字幕和原 MP4Box 集成需要提供该目录；省略 `--toolbox` 时跳过这两项检查，并在报告中记录。

| 命令 | 作用 |
|---|---|
| `doctor` | 检查构建工具 |
| `prepare` | 获取固定版本依赖、校验开发包并应用补丁 |
| `build` | 编译 x264 64 位 8bit 与 x265 64 位 8bit、10bit 编码器；可用 `--encoder x264` 或 `--encoder x265` 单独构建 |
| `verify` | 使用自动生成的素材验证输入、输出及集成 |
| `package` | 检查产物验证记录，生成 ZIP 和 SHA256 文件 |

输出归档位于 `dist/`，包含编码器、FFmpeg、运行 DLL、安装说明、manifest 和许可证。构建脚本负责生成文件，release 由维护者上传。

## 项目结构

```text
AGENTS.md                  AI 接手说明
dependencies.lock.json     固定提交、版本、下载地址和哈希
scripts/project.py         依赖准备、构建、验证、打包入口
scripts/build.sh           Git Bash / MinGW 构建步骤
patches/                   最小兼容性补丁
docs/                      兼容范围和维护流程
packaging/README.md         随 release 包发放的说明
vendor/                    源码及 FFmpeg 开发依赖缓存，不发放
build/                     构建日志、自动生成的验证素材，不发放
dist/overlay/              tools、说明、manifest 和许可证
dist/*.zip                 release 候选包
```

## 已完成验证

18 项自动化检查通过，覆盖 FFmpeg 版本、x264 中文 MP4 输入、x265 8bit 与 10bit 的完整原参数和 Y4M 管道、缩放、字幕、AAC 提取与转码、原 MP4Box 合并及输出解码。x264 另有一次小丸界面单视频正常压制的试用反馈。

详细能力见 [兼容性说明](docs/COMPATIBILITY.md)。更新依赖和维护 release 的步骤见 [维护流程](docs/MAINTENANCE.md)。

## 来源与许可证

- https://maruko.appinn.me/7mod.html
- https://maruko.appinn.me/7mod_feature.html
- https://github.com/jpsdr/x264/tree/t_mod_New
- https://bitbucket.org/multicoreware/x265_git/
- https://github.com/l-smash/l-smash
- https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2

上游许可证保留在 vendor 和 release 包。公开分发时提供本项目对应版本的构建脚本、锁定依赖和补丁，并满足上游对应源码的分发要求。
