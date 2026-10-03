# maruko_tool_update — 小丸工具箱工具更新包

退出小丸，备份对应原文件，将包中 tools/ 的全部文件复制到小丸安装目录的 tools/，覆盖同名文件，无须改名。

包内包含 x264_64-8bit.exe、x265_64-8bit[gcc].exe、独立 ffmpeg.exe，以及配套 FFmpeg DLL。准确文件清单、版本和哈希见 manifest.json。三个 EXE 和全部 DLL 一同复制到 tools/。

本包更新 x264、x265 编码器和小丸调用的 ffmpeg.exe。x264 字幕使用小丸原 VSFilter64.dll；x265 的解码、缩放和字幕由 FFmpeg 处理，合并使用原 MP4Box.exe。

13 项自动化检查通过，覆盖两条视频编码工作流、缩放、字幕、音频处理和合并；x264 另有一次小丸 UI 单视频正常压制的试用反馈。具体自动化验证记录见 manifest.json。

不要混用不同包的 EXE 和 DLL。恢复时还原备份的 x264、x265 和 ffmpeg.exe，不盲目删除其他工具可能依赖的 DLL。许可证位于 licenses/，源码和构建方式由 maruko_tool_update 项目提供。

FFmpeg 上游构建提供的版本、源码提交链接和构建信息位于 third-party/FFmpeg-build-info.txt。x264 使用 manifest 中固定的 t_mod_New 提交，并应用 third-party/ 中的补丁；完整构建步骤位于项目源码仓库。

x265 使用 manifest 中固定的官方源码提交，静态链接 C/C++ 运行时，无需额外的 x265 DLL。旧版 MP4Box 导入带 B 帧的 HEVC 时会产生重排起始偏移；测试中旧、新 x265 的轨道时间一致，manifest 记录了合并后的时间信息。
