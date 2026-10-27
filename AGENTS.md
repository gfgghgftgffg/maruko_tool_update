# AI 接手说明

## 项目目标

维护两条独立入口：小丸工具箱的命令行工具构建与覆盖包，以及根目录的 x265 / AV1 独立压制界面。保留小丸原 UI、原文件名和用户压制偏好；独立界面不改造小丸本体。

EXE 使用 x264_64-8bit.exe、x265_64-8bit[gcc].exe、x265_64-10bit[gcc].exe、ffmpeg.exe 等小丸原名，不加 modern、new 后缀。运行 DLL 随 tools 交付；源码、开发包、测试视频和个人路径不进入 release。

没有明确授权，不修改现有小丸，不发布 release、上传资产或替换系统 FFmpeg。项目内构建、修复、验证和准备候选 ZIP 可直接进行。

## 当前实现与缺口

- 依赖与提交见 dependencies.lock.json；当前源码是 jpsdr/x264 的 t_mod_New，不是取得了原小丸完整 7mod 源码。
- FFmpeg 9.0.2 shared 提供开发头文件、导入库和运行 DLL；静态 ffmpeg.exe 不能作为开发库。
- 覆盖包还包含同一构建的独立 ffmpeg.exe 与全部七个运行 DLL。修改版本或依赖时同时维护 EXE、DLL 清单及音频测试。
- L-SMASH 提供 MP4 输出。关闭旧内部音频代码，保留小丸外部 FFmpeg、MP4Box 工作流。
- patches 中补丁在关闭音频时跳过旧 lsmash_importer.h，没有改变编码算法。
- x265 来自官方 Bitbucket 仓库的固定提交。小丸使用 FFmpeg → Y4M → x265 → 原 MP4Box 工作流；测试参数来自小丸的实际命令生成逻辑。静态编译 64 位 8bit 与 10bit，保留完整原参数，不用 libx265 命令代替独立程序；两者只是 `HIGH_BIT_DEPTH` 编译开关不同，命令行接口一致。
- 当前交付 Windows x64 的 x264 8bit、x265 8bit/10bit 和 FFmpeg。公开说明只描述已经实现、交付和验证的内容。
- x264 输入采用 lavf，x265 输入采用 Y4M 管道。验证覆盖 18 项自动化检查；x264 另有一次单视频 UI 试用反馈，不要扩大验证结论。
- 原 MP4Box 对 HEVC B 帧产生重排起始偏移；测试旧、新 x265 的轨道时间一致。检查有效轨道时长和帧率，不能拿容器总时长与视频时长简单作差。

## 环境

使用 Python 3.11 或更高版本；管理脚本和编码核心仅依赖标准库，界面使用 Tk 与 requirements.txt 中的 tkinterdnd2。虚拟环境和 Python 安装方式由开发者选择，项目不绑定个人解释器路径。所有平台启动器支持 MARUKO_PYTHON、激活环境和项目 .venv；Windows 使用 .cmd，macOS 提供 .command，macOS/Linux 提供 .sh。

构建依赖 Git Bash、MinGW-w64 GCC、mingw32-make、NASM、CMake、Ninja、Windows tar。MARUKO_BASH 和 MARUKO_TOOLCHAIN 可指定路径。x265 在非 ASCII 源码路径下使用 Public 目录的 ASCII 构建缓存和目录联接；MARUKO_BUILD_CACHE 可指定缓存位置。不要删除目录联接所指向的源码。

## 必须遵循的流程

1. 读 README、lock、docs；重要判断看对应源码，不仅看摘要。
2. 更新上游时固定提交、下载地址、哈希和 DLL 依赖，保留本地修改，不强制 reset/clean。
3. 使用 scripts/project.py 的 prepare/build/verify/package。修复因变更导致的失败，检查与变更匹配的范围。
4. 每个位深独立验证，报告绑定 EXE 和 DLL 哈希。修订扩展时同步补丁、能力声明和验证入口。
5. 包内文件名直接对应小丸，manifest 记录来源、版本、哈希、验证结果和缺口。
6. 命令行验证不等于 UI、所有格式或画质速度验证。发布前执行 docs/MAINTENANCE.md 的验收；缺口尚在就明确标为候选。

## 独立压制工具

- gui.py 与 encode.py 只提供 x265、SVT-AV1。x264 仅保留在原有构建流程中。默认 10bit，界面编码器标签必须显示实际位深。
- config.example.json 是可入库模板；config.json 是个人配置，不入库。迁移和重构不改用户 CRF 或高级画质参数；AV1 闭合 GOP 和随机访问检查属于兼容性保护。
- GUI 与 CLI 共用 resolve_paths；优先显式配置，其后查找项目工具目录、构建产物、vendor 和 PATH。不要在代码里写个人绝对路径。
- UI 保持简洁，只保留操作项和必要状态，不添加“保留你的参数”等解释性文案。
- 工具路径通过界面“工具设置”或本地 config.json 配置；check_tools.py --smoke 用合成短片检查版本、参数兼容性与位深。工具二进制不通过 pip 安装，跨平台说明见 docs/TOOLS.md。
- 运行 python -m unittest test_encode test_gui test_tools -v；GUI 测试需要桌面会话。测试通过不等于 macOS/Linux 已验收，也不等于小丸原 UI 已验收。
- jobs、research、compare_1080p、个人测试视频及旧配置备份不属于项目目录，应放在项目外，不只是用 .gitignore 隐藏。个人 config.json、.venv 以及标准 build、vendor、dist 产物不提交、不推送。提交前检查 git status 和忽略规则；发布前检查归档显式文件清单。
- scripts/project.py package 仍仅打包小丸工具覆盖包，不自动包含独立压制界面，也不自动发布。

## 清理

vendor 为可恢复的源码和开发依赖，build、dist 为生成目录。删除或移动前检查绝对路径在本项目内；保留用户额外修改，禁止盲目递归删除。项目不保留个人测试视频。不要改 CRF 等参数来掩盖兼容问题。
