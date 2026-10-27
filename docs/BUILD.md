# 构建小丸工具更新包

此流程用于 Windows x64 小丸工具覆盖包；独立 x265 / AV1 压制界面的运行不需要编译这些源码，见 [压制使用说明](ENCODING.md)。

## 环境

- Python 3.11+、Git for Windows（含 Git Bash）。
- MinGW-w64 x64 工具链，含 GCC、`mingw32-make`、NASM。
- CMake、Ninja，用于构建 x265。
- 支持 7z 的 Windows `tar`。

已验证工具链为 GCC 14.2.0、NASM 2.16.01、CMake 3.30.4、Ninja 1.12.1。依赖的提交、下载地址、哈希和运行库清单见 [dependencies.lock.json](../dependencies.lock.json)。

| 可选环境变量 | 作用 |
|---|---|
| `MARUKO_BASH` | Git Bash 的 `bash.exe` 路径 |
| `MARUKO_TOOLCHAIN` | MinGW-w64 的 `bin` 目录 |
| `MARUKO_BUILD_CACHE` | x265 构建缓存，必须使用 ASCII 路径 |

工具默认从 PATH 和 Git 安装目录发现。源码路径包含非 ASCII 字符时，x265 的 NASM 构建通过 Windows Public 目录中的缓存及源码目录联接处理；也可用 `MARUKO_BUILD_CACHE` 指定位置。不要删除联接指向的源码。

## 执行

在项目根目录运行：

```powershell
python scripts/project.py doctor
python scripts/project.py prepare
python scripts/project.py build --encoder all --bit-depth 8
python scripts/project.py verify --bit-depth 8 --toolbox "<小丸安装目录>"
python scripts/project.py package --bit-depth 8
```

| 命令 | 作用 |
|---|---|
| `doctor` | 检查构建工具 |
| `prepare` | 获取锁定版本，校验 FFmpeg 开发包并应用补丁 |
| `build` | 编译 x264 8bit、x265 8bit 与 10bit；可用 `--encoder x264` 或 `--encoder x265` 单独选择 |
| `verify` | 生成测试素材，验证输入、输出及小丸集成 |
| `package` | 核对产物与通过验证的哈希，生成 ZIP 和 SHA256 |

这里的 `--bit-depth 8` 指 x264 的构建配置；x265 的 8bit 和 10bit 程序都会生成。独立压制界面默认使用 **x265 10bit**。

字幕和原 MP4Box 集成验证需要 `--toolbox` 指向已有小丸目录。省略时跳过对应项目，并记录在报告中；不能据此宣称完整通过。

## 产物

- `vendor/`：源码、FFmpeg 开发头文件和库，只作本地依赖缓存。
- `build/`：构建日志、验证报告、合成测试素材。
- `dist/overlay/`：工具覆盖包目录，包含 `tools/`、说明、manifest、许可证与构建信息。
- `dist/*.zip`、`*.zip.sha256`：待验收的候选包。

包内程序沿用小丸原名，FFmpeg EXE 与全部配套 DLL 一起交付。x265 通过 FFmpeg → Y4M → 独立 x265 → 原 MP4Box 工作，不改写为 libx265 调用。

打包不会收集根目录的个人配置、任务记录、研究目录或测试素材，也不包含独立压制界面。脚本不安装到小丸目录，不上传或发布 release。

后续更新及发布前验收见 [维护流程](MAINTENANCE.md)，上游来源见 [第三方组件](THIRD_PARTY.md)。
