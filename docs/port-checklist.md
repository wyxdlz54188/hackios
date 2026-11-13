# 移植清单：OnePlus 8T，iOS 17.0.0

顺序沿用上游 `docs/porting/index.md`：**先能启动，再一个部件一个部件地做**。每一步都写了"做完了怎么算"，
没做到的不要标 `works`（`device.conf` 的 status 是唯一状态来源）。

## 第 0 步：UEFI —— 不写平台，先验证已有的 kebab

Mu-Silicium 已经带 `Platforms/OnePlus/kebabPkg`，而**本机就是 kebab 板**（KB2000 8T：指纹
`OnePlus/OnePlus8T_CH/OnePlus8T`、面板 `amb655x`、地址逐段对得上）。所以这一步不是"写平台"，是"验证"。
完整论证、比对输出和两个值得盯的内存窗口在 `uefi/README.md` 与 `docs/uefi-map-report.md`。

- [x] 把本机设备树拉下来，与 kebab 的 `MemoryMapLib.c` 逐段比对（`tools/check-uefi-map.py`）
- [ ] 在 Linux 上 `uefi/apply.sh`（= `uefi/apply.sh kebab`）+ `build_uefi.py -d kebab -r RELEASE`
- [ ] `./xl enter`，确认 `./xl screenshot` 有 HakiOS logo、`./xl log` 有 UEFI 第一行日志

**算完的标志**：屏幕出现 logo，loader banner 出来。若卡在写日志/堆：先把 kebab 的 `DXE Heap` 从
`0xB0000000 +69 MB` 挪到 `0xB0400000 +65 MB`（避开本机的 `ramoops@0xB0000000 +4 MB`），再试。

> 注意别被 `ro.boot.project_codename=instantnoodle` 引到 OnePlus 8 的平台上去 —— 那是 ABL 报的板族名，
> 市场名与指纹才是 8T。

## 第 1 步：仓库与配置（本仓库已经做完）

- [x] `device.conf`、`configs/oneplus8t_defconfig`、`configs/oneplus8t.config`、`soc/`（sm8250）、`soc.args`
- [x] `prebuilt/device-tree.dtb`（本机 `/sys/firmware/fdt`，787 882 字节）
- [x] `tools/soc-args-kona.py` 在真机 DT 上产出与 `soc.args` 完全一致的结果
- [ ] 在公共仓库里跑 `tools/hakios-device.py check oneplus8t`（需要 Linux 侧，尚未跑）

## 第 2 步：第一次启动，什么驱动都不要

```sh
make oneplus8t_defconfig && make config
make kernel && make loader
make phone SECS=120
```

**算完的标志**：loader banner 之后，内核打印 `hakios-kernel: N drivers built in`（N 很小），
launchd 起来，然后自己结束、手机回到 Android。

这一步最容易卡在 `soc_mpss_mem` 上：本机 DT 没有 modem 保留区，内核默认值是参考机的。**第一次启动前**
必须把它补上（见 `docs/device-report.md` 第 3 节），否则 modem 相关的地址是错的。

## 第 3 步：驱动，按上游给的顺序

| 序 | 部件 | 这台机器的实际情况 | 要做的事 |
|---|---|---|---|
| 1 | `CPUFREQ` `THERMAL` `SOCINFO` | 地址与上游驱动**一致**：EPSS `0x18591000` 三域、TSENS TM `0xc263000`/`0xc265000`、SMEM `0x80900000`（`docs/kona-soc-facts.md`） | `CPUFREQ`/`SOCINFO` 不用改；`THERMAL` **只换传感器表**（`soc/thermal/kona-thermal-table.h`，25 个，`tools/dt-thermal.py` 从本机 DT 生成） |
| 2 | `BUTTONS` | `qpnp_pon` + `gpio-keys` + 霍尔 | 改 PMIC 寄存器地址（PM8150 系列与参考机不同） |
| 3 | 触摸 | **Synaptics S3908**（i2c `0xa94000`，`0x4B`） | 上游只有 Goodix/FocalTech，**要新写 `hakios.synaptics.c`**；寄存器手册与初始化表从本机 `libpanel`/内核取 |
| 4 | `UFS` | UFS 3.1，`1d84000.ufshc` | 上游 `hakios.ufs.c`/`ufshc.c` 是 sc7280 的 UFSHC 基址，改基址与 PHY 表后只读验证 |
| 5 | `ADRENO` | 650（`a650_*` 固件） | 上游是 642L；GPU 表、GMU 固件名、ringbuffer 都要换；`hakios-metal` 的 a6xx 表也要补 650 |
| 6 | `ADSP` `BATTERY` `SPEAKER` `SOUND` `MIC` | WCD938x + Bolero | DSP 的 QMI 服务地址改为 kona 的；编解码器的寄存器与参考机完全不同 |
| 7 | `WIFI`（+`QMI`） | **QCA6390** | 上游是 WCN6750/ath11k；QCA6390 走 PCIe + `qcom,cnss-qca6390`，**不是同一条路** |
| 8 | `HAPTIC` | PM8150B haptics | 上游是 Awinic AW86927；PM8150B 是 ff-memless，改驱动或用新的 |
| 9 | `CAMERA` `TORCH` `MODEM` `BT` | — | 最后做 |

**算完的标志**：每个部件在 `device.conf` 里从 `missing` 改成 `works`/`partial`，并写清它是怎么打开的。

## 第 4 步：文档与发布

```sh
python3 tools/check-port.py .
```

（公共仓库里是 `tools/docs-gen.py` + `tools/hakios-device.py check`。）然后把仓库拆出去命名
`hakios-oneplus8t`，在 `devices/manifest.conf` 里加一段。

## 与 iOS 17.0.0 相关的额外步骤（本仓库已完成补丁层）

1. 内核：用 `ios17/hakios-xnu-10002.1.13.patch`，而不是上游的 `xnu/hakios.patch`
   （`ios17/apply.sh` 一键建树）。变基报告见 `ios17/REBASE.md`。
2. 用户态：需要 **A12 及以上**机型的 iOS 17.0.0 IPSW（17.0 不再支持 iPhone X，所以上游用的
   `iPhone10,3/10,6 16.5 20F66` 不能用了）。建议 `iPhone11,2 (XS) 17.0.0 21A329`：
   `sysimage/unpack.sh` 里的成员名、大小、dyld cache 目录名、`select-system.py` 的文件清单都要按新 IPSW 改。
3. 编译：`xnu-deps/setup.sh` 的 SDK 覆盖与两个外部库要按 10002 重做（`--rebuild-libs`）；
   `tools/` 里假定 `xnu-8796.121.2` 路径的地方都要跟着改（`xnu-build.sh`、`apply.sh`、`Makefile`）。
4. 驱动：`drivers/` 里 49 个驱动对 10002 的编译还没有人验证过 —— 这是补丁层之后的第一件事。
