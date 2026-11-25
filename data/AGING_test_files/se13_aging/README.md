# SE13 老化包存放目录

老化包体积大（约 2.4GB），不纳入 git。请将 `cv84x6_soc_aging.tgz` 放入本目录：

```
data/AGING_test_files/se13_aging/
├── cv84x6_soc_aging.tgz      # 本地放置，不入库
├── cv84x6_soc_aging.MD5      # 校验文件（入库）
└── README.md
```

校验：

```bash
cd data/AGING_test_files/se13_aging
md5sum -c cv84x6_soc_aging.MD5
```

平台在老化测试时会自动选择该包并上传到设备 `/data/cv84x6_soc_aging/`。
