# maruko_tool_update — 小丸工具箱工具更新包

退出小丸，备份对应原文件，将包中 tools/ 的全部文件复制到小丸安装目录的 tools/，覆盖同名文件，无须改名。

包内包含指定输出位深的 x264_64-8bit.exe 或 x264_64-10bit.exe、独立 ffmpeg.exe，以及配套 FFmpeg DLL。准确文件清单、位深、版本和哈希见 manifest.json。两个 EXE 和全部 DLL 必须一同安装。

本包更新对应 x264 编码器和小丸调用的 ffmpeg.exe，不更新 UI、配置、MP4Box.exe、其他位深或 x265。字幕继续使用小丸原 VSFilter64.dll。

当前属于命令行验证候选。UI、批量和取消未验证；FFMS、AviSynth 和 7mod keyint auto 未恢复。验证范围与跳过项目见 manifest。10bit 必须独立构建验证后进入相应包。

不要混用不同包的 EXE 和 DLL。恢复时还原备份的 x264 和 ffmpeg.exe，不盲目删除其他工具可能依赖的 DLL。许可证位于 licenses/，源码和构建方式由 maruko_tool_update 项目提供。

FFmpeg 上游构建提供的版本、源码提交链接和构建信息位于 third-party/FFmpeg-build-info.txt。x264 使用 manifest 中固定的 t_mod_New 提交，并应用 third-party/ 中的补丁；完整构建步骤位于项目源码仓库。
