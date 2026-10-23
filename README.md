# Athena2 Web Product Test

> 嵌入式设备产测工具 — 从 QT 桌面应用迁移至 Web 网页方式，支持 SE9/SE12/EVB 等 CVITEK 芯片平台。



## 版本

[![Release](https://img.shields.io/badge/release-v2.0.1-blue)](https://github.com/Xuan-yangyi/product_test/releases)
[![Main](https://img.shields.io/badge/main-development-orange)](https://github.com/Xuan-yangyi/product_test)

> **生产部署请使用 Release 版本**: `git clone https://github.com/Xuan-yangyi/product_test.git && cd product_test && git checkout v2.0.1 && ./init.sh`
> **开发调试请使用 main 分支**: `git clone https://github.com/Xuan-yangyi/product_test.git && cd product_test && ./init.sh`

> ⚠️ **老化测试需要额外下载老化包**: Release 版本不包含老化测试二进制文件（体积过大，约 5.2GB）。
> 请从 [Wiki 页面](https://wiki.sophgo.com/pages/viewpage.action?pageId=163064732) 下载 `athena2_soc_aging_v1_2_5.tgz`，
> 解压到 `data/AGING_test_files/soc_aging/` 目录下。

## 架构
