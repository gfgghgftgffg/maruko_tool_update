# AI 接手说明

## 项目目标

持续维护小丸工具箱调用的命令行工具，交付按原路径覆盖的 release 包。保留 UI、用户参数和原文件名，不自行重写 UI 或调整压制偏好。

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

使用 Python 3.11 或更高版本，管理脚本仅依赖标准库。虚拟环境和 Python 安装方式由开发者选择，项目不绑定个人解释器路径。

构建依赖 Git Bash、MinGW-w64 GCC、mingw32-make、NASM、CMake、Ninja、Windows tar。MARUKO_BASH 和 MARUKO_TOOLCHAIN 可指定路径。x265 在非 ASCII 源码路径下使用 Public 目录的 ASCII 构建缓存和目录联接；MARUKO_BUILD_CACHE 可指定缓存位置。不要删除目录联接所指向的源码。

## 必须遵循的流程

1. 读 README、lock、docs；重要判断看对应源码，不仅看摘要。
2. 更新上游时固定提交、下载地址、哈希和 DLL 依赖，保留本地修改，不强制 reset/clean。
3. 使用 scripts/project.py 的 prepare/build/verify/package。修复因变更导致的失败，检查与变更匹配的范围。
4. 每个位深独立验证，报告绑定 EXE 和 DLL 哈希。修订扩展时同步补丁、能力声明和验证入口。
5. 包内文件名直接对应小丸，manifest 记录来源、版本、哈希、验证结果和缺口。
6. 命令行验证不等于 UI、所有格式或画质速度验证。发布前执行 docs/MAINTENANCE.md 的验收；缺口尚在就明确标为候选。

## 清理

vendor 为可恢复的源码和开发依赖，build、dist 为生成目录。删除或移动前检查绝对路径在本项目内；保留用户额外修改，禁止盲目递归删除。项目不保留个人测试视频。不要改 CRF 等参数来掩盖兼容问题。
