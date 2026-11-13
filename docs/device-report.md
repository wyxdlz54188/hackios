# 设备数据报告：OnePlus 8T (KB2000)

本文件里的每一个数字都是 2026-11-13 从这台真机上读出来的（`adb` + root，序列号 `c8646380`），
不是从网上抄的，也不是估的。每一项后面写着读取方式，方便复核。

## 1. 身份与系统

| 项 | 值 | 来源 |
|---|---|---|
| 型号 / 代号 | `KB2000` / `OnePlus8T`，项目代号 `instantnoodle`（DTB `project_codename`） | `getprop ro.product.model`, `ro.boot.project_codename` |
| 厂商 | OnePlus（`ro.product.brand`），`ro.product.hw=AE008` | `getprop` |
| 序列号 | `c8646380` | `getprop ro.boot.serialno` |
| 系统 | Android 14，`UKQ1.230924.001`，版本串 `R.1983865_1_2` | `getprop ro.build.fingerprint` |
| Build 类型 | `user` / `release-keys`（**不是** userdebug） | `getprop ro.build.type`, `ro.build.tags` |
| 内核 | Linux `4.19.157-perf+`，clang 10.0.7，2024-08-14 构建 | `cat /proc/version` |
| API / ABI | SDK 34，`arm64-v8a`，page size 4096 | `getprop` |
| 分区方案 | A/B + dynamic partitions（`super`），slot `_a` | `ro.boot.slot_suffix`, `ro.product.ab_ota_partitions` |
| Root | Magisk（`id` → `context=u:r:magisk:s0`） | `adb shell su -c id` |

**引导状态要看内核命令行，不要看 `getprop`**。这台机器的 `getprop ro.boot.flash.locked` 报 `1`、
`verifiedbootstate=green`，而同一台机器的 `/proc/cmdline` 写着：

```
androidboot.vbmeta.device_state=unlocked androidboot.verifiedbootstate=orange
```

cmdline 是 bootloader 亲手传的，`getprop` 的这两项可被 root 模块伪造。上游 `docs/windows.md`
专门警告过这一点（"Trust the device tree, not the product name"）。移植以 cmdline 为准。

## 2. SoC 与平台地址（SM8250 "kona"）

| 块 | 地址 | 来源（设备树节点） |
|---|---|---|
| GICv3 | `0x17a00000` | `/soc/interrupt-controller@17a00000`（`arm,gic-v3`） |
| 串口（console/earlycon） | `0xa90000` | `cmdline: earlycon=msm_geni_serial,0xa90000 console=ttyMSM0,115200n8` |
| UFS 主控 | `0x1d84000`（`soc/1d84000.ufshc`） | `ro.boot.boot_devices`, `ro.boot.bootdevice` |
| USB | `0xa600000.dwc3` | `ro.boot.usbcontroller` |
| IPCC | `0x408000` | `/soc/qcom,ipcc@408000` |
| RPMh RSC | `0x18220000` | `/soc/qcom,rpmh-rsc@18200000`（`reg` 第 3 组） |
| AOSS / QMP | `0xc300000` | `/soc/qcom,qmp-aop@c300000` |
| IPA | `0x1e00000`，寄存器基址 `0x1e40000`，GSI `0x1e04000` | `/soc/qcom,ipa@1e00000`（`reg` 两组） |
| 应用侧 SMMU | `0x15000000` | `/soc/apps-smmu@15000000` |
| SMEM | `0x80900000` | `/reserved-memory/smem_region@80900000`，经 `/soc/qcom,smem` 的 `memory-region` |
| IMEM | `0x146bf000`，按 2 MB 对齐取 `0x14600000` | `/soc/qcom,msm-imem@146bf000` |
| Command DB | `0x80860000` | `/reserved-memory/reserved-memory@80860000`，compatible `qcom,cmd-db` |
| IPA 固件装载点 | `0x8e210000` | `/reserved-memory/pil_ipa_gsi_region@8e210000` |
| IPA pas-id | `0xf` | `/soc/qcom,ipa_fws` 的 `qcom,pas-id` |
| IPA 固件名 | `ipa_fws` | 同上，`qcom,firmware-name` |

CPU：8 核，`cpu0-3` = Cortex-A55（能效核），`cpu4-6` = Cortex-A77（大核），`cpu7` = Cortex-A77 超大核，
所以 `CONFIG_BOOTCPU=7`。PMIC：`PM8150` / `PM8150B` / `PM8150L`，都在 `spmi@c440000`（`spmi0-00`、`-03`、`-05`）。

## 3. 内存与保留区

`MemTotal: 11776944 kB`（12 GB 机型）。设备树里的保留区（地址取自节点名 / `reg`）：

| 用途 | 地址 | 节点 |
|---|---|---|
| hypervisor | `0x80000000` | `hyp_region@80000000` |
| XBL / AOP | `0x80700000` | `xbl_aop_region@80700000` |
| Command DB（0x20000 大） | `0x80860000` | `reserved-memory@80860000` |
| SMEM | `0x80900000` | `smem_region@80900000` |
| 相机 / WLAN / IPA / IPA GSI / GPU / NPU / video / CVP / CDSP / SLPI / ADSP / SPSS PIL | `0x8dc00000`, `0x8e100000`, `0x8e200000`, `0x8e210000`, `0x8e21a000`, `0x8e300000`, `0x8e800000`, `0x8ed00000`, `0x8f200000`, `0x90600000`, `0x91b00000`, `0x94000000` | `pil_*_region@...` |
| CDSP secure heap | `0x94100000` | `cdsp_secure_heap@94100000` |
| 开机 logo / display rdump | `0x9c000000` | `cont_splash_region@9c000000`、`disp_rdump_region@9c000000` |
| DFPS 数据 | `0x9e300000` | `dfps_data_region@9e300000` |
| U-Boot 日志（OnePlus 自有） | `0x9FE00000` | `kboot_uboot_logmem@0x9FE00000` |
| ramoops | `0xB0000000` | `ramoops@0xB0000000` |

**这台机器的设备树里没有 modem 的保留区节点。** 这是移植里唯一一个"第一次启动就需要、但树给不出来"的
值（`soc_mpss_mem`），也是同样原因没有 `qcom,mss` 节点（`soc_pas_mpss` 缺）。上游文档说得很清楚：
树里没有的值就报"缺"，不要猜。补齐办法：从本机的 `uefi`/`dtbo` 或 SDX55 的 image 表里取，或者由
UEFI 平台在给内核准备内存描述时直接给出。

## 4. 显示

- 面板：`qcom,mdss_dsi_oplus20828samsung_amb655x_1080_2400_cmd`（`/proc/cmdline` 的 `msm_drm.dsi_display0`），
  Samsung AMB655 驱动 IC，**1080x2400，cmd 模式 DSI，120 Hz**。
- 显示控制器：SDE（`/sys/class/drm/sde-crtc-0..4`），`card0-DSI-1`、`card0-DP-1`。
- 电源：`/soc/dsi_panel_pwr_supply`（3 路）与 `dsi_panel_pwr_supply_lab_ibb`（3 路）。
- 保留区：`cont_splash_region@9c000000`（开机图）。

HakiOS 现在只能用 UEFI 的 framebuffer 画；kona 的 SDE/DSI 驱动要新写，面板初始化序列得从本机
`/vendor/lib64/libpanel.so` 或内核里那份 DSI 表取（厂商固件，不进仓库）。

## 5. 触摸、按键、马达

- 触摸：**Synaptics S3908**，I2C `i2c@a94000`，地址 `0x4B`（节点 `/soc/i2c@a94000/synaptics_19805@4B`，
  compatible `synaptics-s3908`）。Android 侧只有一个虚拟设备 `touchpanel`（`/proc/bus/input/devices`），
  真正的 IC 由 `oplus` 的触摸抽象层驱动。
- 触摸按键：`touchpanel_kpd`（虚拟）。
- 按键：`gpio-keys`（`soc:gpio_keys`）+ `qpnp_pon`（PM8150 `qcom,power-on@800`）+ `oplus,hall_tri_state_key`（霍尔）。
- 马达：**PM8150B haptics**（`spmi0-03`，`qcom,haptics@c000`，输入设备 `qti-haptics`，ff-memless），
  **不是**参考机的 Awinic AW86927。

## 6. 存储

UFS 3.1，256 GB（`sda` = 247013376 KB）。`/proc/partitions` + `/dev/block/by-name` 实测的主要分区：

| 分区 | 设备 | 用途 |
|---|---|---|
| `xbl_a` / `xbl_b` | `sdb1` / `sdc1` | bootloader 链 |
| `abl_a` / `abl_b` | `sde8` / `sde32` | ABL |
| `boot_a` / `boot_b` | `sde11` / `sde35` | 内核 + ramdisk |
| `dtbo_a` / `dtbo_b` | `sde17` / `sde41` | 设备树 overlay（`dtbo_idx=3`） |
| `super` | `sda15` | 动态分区（system/vendor/product…） |
| `metadata` | `sda20` | 元数据 |
| `userdata` | `sda28` | 用户数据（`darwin` 分区要从这里切） |
| `logdump` | `sde57` | loader 日志（上游默认往这里写几 KB） |
| `uefivarstore` | `sde59` | **UEFI 变量存储，本机自带** |
| `op1` / `op2` | `sde66` / `sda11` | OnePlus 自有 |
| `persist` | `sda2` | 传感器/校准，**绝不可写** |
| `modemst1`/`modemst2` | `sdf2`/`sdf3` | modem 校准，**绝不可写** |

`darwin` 分区当前**不存在**，要用上游 `tools/userdata-carve.py` 从 `userdata` 尾部切（只打印计划，不写）。

## 7. GPU

`/sys/class/kgsl/kgsl-3d0/gpu_model` = `Adreno650v3`（Adreno 650）。固件在
`/vendor/firmware/a650_gmu.bin`、`a650_sqe.fw`、`a650_zap.mdt/b00..b02`。

注意：`hakios-metal/` 只认 chip id `0x06030500`（Adreno 642L），别的 Adreno 会被
`hakios_metal_open()` 拒绝并回落到 OpenGL ES —— 650 要按 `docs/reference/metal.md` 自己补一张表
（Mesa 的 `freedreno_devices.py` 是起点）。

## 8. Wi-Fi / 蓝牙

- Wi-Fi：**QCA6390**，PCIe 上的 `qcom,cnss-qca6390@b0000000`（不是参考机的 WCN6750/ath11k）。
  板级数据在 `/vendor/firmware/wlan/qca_cld/`，无线电镜像在 `/vendor/firmware_mnt/image/wpss.*`。
- 蓝牙：QCA6390 的 SLIMbus 半边，`/soc/slim@3ac0000/qca6390`（`qcom,btfmslim_slave`）。
- IPA 的 WLAN SMMU 回调：`/soc/qcom,ipa@1e00000/ipa_smmu_wlan`。

## 9. 音频与电池

- 编解码器：**WCD938x** + Bolero 的 RX/TX macro（`/soc/qcom,msm-audio-apr/qcom,q6core-audio/bolero-cdc/`）。
- ALSA 声卡：`kona-mtp-snd-card`（`/proc/bus/input/devices` 里的 Headset/Button Jack）。
- 电池电量走 ADSP（与参考机相同路径），所以 `ADSP` 不通之前 `BATTERY` 也没有。
- DSP 镜像：`/vendor/firmware_mnt/image/adsp.*`。

## 10. 基带

- `ro.boot.baseband=mdm`，即 SDX55。IPA 在 SoC 里（`0x1e00000`），有 4 个 SMMU 回调：
  `ipa_smmu_ap`（stream `0x5c0`）、`ipa_smmu_uc`（`0x5c2`）、`ipa_smmu_wlan`、`ipa_smmu_11ad`。
- GLINK/QRTR 端点：`/soc/qcom,glink/{adsp,cdsp,dsps,spss,npu}`。
- 上游 `docs/cellular.md` 里的 IPA 布局是按 IPA 4.11 写的；**kona 的 IPA 版本要在写驱动时先确认**
  （读 `/soc/qcom,ipa@1e00000` 的 `qcom,ipa-hw-ver`，本报告未取）。

## 11. 这份报告是怎么来的（可复现）

```sh
adb devices -l
adb shell 'su -c "getprop | grep -E \"ro\.(product|build|boot|soc|hardware)\""'
adb shell 'su -c "cat /proc/cmdline; cat /proc/version"'
adb shell 'su -c "cat /proc/partitions; ls -l /dev/block/by-name"'
adb shell 'su -c "cat /proc/bus/input/devices"'
adb shell 'su -c "cat /sys/class/kgsl/kgsl-3d0/gpu_model"'
adb shell 'su -c "cat /sys/firmware/fdt > /data/local/tmp/hakios-fdt"'
adb pull /data/local/tmp/hakios-fdt prebuilt/device-tree.dtb
python3 tools/soc-args-kona.py prebuilt/device-tree.dtb
```

`tools/collect-device.sh` 把上面这些再跑一遍并打印出来。
