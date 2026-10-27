# 第三方组件

## 来源

| 组件 | 上游 |
|---|---|
| 小丸与 7mod 说明 | https://maruko.appinn.me/7mod.html 、https://maruko.appinn.me/7mod_feature.html |
| x264 t_mod_New | https://github.com/jpsdr/x264/tree/t_mod_New |
| 官方 x265 | https://bitbucket.org/multicoreware/x265_git/ |
| L-SMASH | https://github.com/l-smash/l-smash |
| FFmpeg Windows 构建 | https://github.com/GyanD/codexffmpeg/releases/tag/9.0.2 |
| SVT-AV1 | https://gitlab.com/AOMediaCodec/SVT-AV1 |
| tkinterdnd2 | https://github.com/pmgagne/tkinterdnd2 |

构建工具的准确提交、版本、下载地址和校验值记录在 [dependencies.lock.json](../dependencies.lock.json)。界面的 Python 依赖记录在 [requirements.txt](../requirements.txt)。AV1 使用所选 FFmpeg 内置的 libsvtav1，其版本取决于该 FFmpeg 构建。

## 分发

工具更新包保留上游许可证、FFmpeg 构建信息和本项目补丁。公开分发时还需提供对应版本的构建脚本、锁定依赖、补丁和准确的对应源码访问方式，满足各组件的许可证要求。

FFmpeg full 构建的第三方依赖也需要核对，不能用上游首页代替对应源码链接。发布验收见 [维护流程](MAINTENANCE.md)。

独立界面的 Python 依赖通过 pip 安装，不由现有小丸工具覆盖包附带。个人配置、任务记录、视频素材、研究目录和缓存不进入仓库或发布包。
