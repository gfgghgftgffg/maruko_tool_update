# 已完成的兼容性验证

交付环境为 Windows x64，编码输出为 H.264、8bit、4:2:0。视频读取使用 lavf，音频由独立 FFmpeg 处理，MP4 合并使用小丸原 MP4Box。

## 自动化检查

| 检查 | 结果 |
|---|---|
| 包内 FFmpeg 版本 | 9.0.2，启动正常 |
| 中文路径 MP4 输入和 CRF 编码 | 通过；输出 yuv420p，帧数与尺寸正确 |
| 小丸格式的缩放参数 | 通过；输出尺寸正确 |
| 原 VSFilter64 字幕烧录 | 通过；生成字幕检查截图 |
| 包内 FFmpeg 提取 AAC | 通过；编码和采样率正确 |
| 包内 FFmpeg 转码 AAC | 通过；48 kHz、双声道 |
| 原 MP4Box 合并音视频 | 通过；包含 H.264、AAC，时长正确 |
| 输出视频解码 | 通过 |

测试使用 CRF 24、preset 8、ref 4、B 帧 3、umh、scenecut 60、deblock 1:1、qcomp 0.5、psy-rd 0.3:0、AQ 2/0.8。subme 10、me_range 24、lookahead 60 等设置保持。

验证素材由脚本自动生成，记录写入 build/verification-8.json，绑定 EXE 和全部 DLL 的 SHA256。归档中的 manifest.json 包含该记录。

## 实际试用

已收到通过小丸 UI 完成一次单视频正常压制的使用反馈。该反馈与自动化检查分别记录；它代表一个实际任务的通过结果。

参数一致不代表不同编码器版本的像素、码流、体积或速度完全一致。上述结果对应列出的验证场景。
