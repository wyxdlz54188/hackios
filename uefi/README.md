# UEFI：本机是哪块板，用不用新写平台

结论先说：**不用新写平台**。Mu-Silicium（HakiOS 的 UEFI 就是它 + 一个补丁）里已经有
`Platforms/OnePlus/kebabPkg`，而 kebab 就是 OnePlus 8T —— 这台 KB2000 的板子。所以我们这一层的
工作是**验证 kebab 平台在本机跑得起来**，而不是造一个 `instantnoodlePkg`。

## 证据：本机就是 kebab

| 本机读到的 | Mu-Silicium 的 kebab |
|---|---|
| `ro.product.model=KB2000`、`ro.product.device=OnePlus8T`、指纹 `OnePlus/OnePlus8T_CH/OnePlus8T:14/...` | `kebabPkg/kebab.dsc` 里 `PcdSmbiosSystemModel\|"8T"`、`PcdSmbiosSystemRetailSku\|"8T_kebab"` |
| 面板 `qcom,mdss_dsi_oplus20828samsung_amb655x_1080_2400_cmd`（cmdline） | `Include/RAW.inc` 里有 `Panel-samsung_amb655x_dsc_cmd.xml`（`Binaries/kebab/RawFiles/`） |
| GIC `0x17a00000`、IPC `0x408000`、SMEM `0x80900000`、cmd-db `0x80860000`、splash `0x9c000000` | `MemoryMapLib.c` 里同样的地址（`AOP CMD DB 0x80860000`、`SMEM 0x80900000`、`Display Reserved 0x9C000000`） |
| `ro.boot.project_codename=instantnoodle` | **不冲突**：这是 ABL 报的板族名，OnePlus 8 系列共用；市场名/指纹才是 8T |

> 也就是说 `instantnoodle` 这个名字会把人引到 OnePlus 8 上去。以 `OnePlus8T` 指纹和 `amb655x` 面板为准，
> 平台选 **kebab**。

## 建与启动

```sh
# 公共仓库根目录
uefi/apply.sh kebab            # Mu-Silicium(BASE) + HakiOS 补丁 + kebab 平台
python3 -m venv venv && venv/bin/pip install -r Mu-Silicium/pip-requirements.txt
cd Mu-Silicium && source ../venv/bin/activate
python3 build_uefi.py -d kebab -r RELEASE     # -> Build/kebabPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd
cd ..
./xl enter
```

（本仓库 `uefi/apply.sh` 是这一条的封装；见下面。）

**算完的标志**：`./xl screenshot` 截到 HakiOS 的 logo，`./xl log` 有 UEFI 的第一行日志
`HakiOS UEFI (Mu-Silicium) for OnePlus 8T`，以及 loader 的 banner。

## 第一次上机（2026-11-13）：还没成功，但知道卡在哪

| 步骤 | 结果 |
|---|---|
| Mu-Silicium 的 kebab 平台 | **编出来了**：`Build/kebabPkg/RELEASE_CLANGPDB/FV/SILICIUM_UEFI.fd`，3 145 728 字节（= `kebab.toml` 的 0x300000） |
| `BootShim.bin` | 编出来了（112 字节，`FD_BASE=0x9FC00000`、`FD_SIZE=0x300000`、`PAYLOAD_BASE=0xF0000000`） |
| 启动镜像 | `uefi/mkimg.py` 打包：gzip(BootShim + FD + XNUP payload) + 本机 DTB，`mkbootimg --header_version 1`，1 812 480 字节 |
| `fastboot boot` | 上传成功（1770 KB，0.07 s），手机随后**掉进 Qualcomm HS-USB Diagnostics 900E**（`VID_05C6 PID_900E`），fastboot/adb 都消失；长按电源 15 秒回到 Android |

两点判断：

1. 那一次用的是**原版 Mu-Silicium**（没打 HakiOS 的补丁），所以它的 BootManagerLib 不会去找
   XNUP 容器里的 loader —— 掉进 900E 不奇怪，但也说明 UEFI 这一步还没被验证过。
2. 要验证得用 HakiOS 的 UEFI：`Mu-Silicium` 在 `uefi/BASE` 那个 commit 上 + `hakios.patch` + `files/`。
   这条路目前卡在两个环境问题上（不是代码）：`Mu_Basecore/.../libspdm` 下 openssl 的 commit 拉不下来，
   以及 `stuart_update` 说外部依赖过期；换目录重新 clone 也一样。

**下一步**：WSL 恢复后，用 `build_uefi.py -d kebab -s`（跳过外部依赖检查）配合一个干净的 BASE 树再试；
再不行就把 `libspdm` 子树从 submodule 里摘掉（SPDM 与 kebab 的启动无关）。

### 后来的进展（同一天，第二轮）

- HakiOS 的 UEFI（Mu-Silicium 在 `BASE` + `hakios.patch` + `files/`）**编出来了**：`uefi-kebab-hakios.fd`
  （3 145 728 字节）。办法是跳过 `edk2toolext` 的外部依赖校验（`libspdm` 子模块里的 openssl/mbedtls
  commit 已从上游消失，`stuart_update` 永远过不去）。
- 打了补丁的 FD 与三个 boot image 变体（`--header_version 1` + DTB、`--header_version 2` + `--dtb`、
  不带 DTB）都试过 `fastboot boot`，**屏幕一直是黑的**，随后进 900E。
- **一个重要的观察**：ABL 会说 `Failed to load/authenticate boot image: Load Error`。这个错误和镜像
  内容无关 —— 同一个被接受过的镜像，在几次 900E 之后也会被拒绝。也就是说它反映的是 **ABL/设备的
  状态**（上一次崩溃留下的标志），不是镜像格式。要重新试，得先把手机完整重启一次。
- 二分用的最小镜像（内核只有 `b .` 两条指令）也准备好了：`xnu-stub-dtb.img`。它的用途是：如果它能
  被接受并且**不再**进 900E（黑屏但一直开着），就说明 ABL→我们镜像的交接是好的，崩的是 UEFI；
  反之则崩在交接之前。

**下一轮的顺序**（手机每次重启后试一个，记录"黑屏/900E/是否还活着"）：

1. `xnu-hakios-nopayload-v1dtb.img`（只有 UEFI，没有 XNUP payload）—— 判断 UEFI 本身能不能跑。
2. `xnu-stub-dtb.img`（只有 `b .`）—— 判断交接本身。
3. `xnu-oneplus8t-hakios.img`（完整：UEFI + loader）—— 前两个都活着时才轮到它。

## 内存映射：kebab 的 vs 本机设备树

`tools/check-uefi-map.py` 把两边逐段比较（`docs/uefi-map-report.md` 是这次运行的完整输出）：

- **42 段** UEFI 映射，本机设备树 **23 段**保留区。
- 23 段里 **20 段**被 kebab 的映射覆盖，地址逐一对得上。
- 3 段没有：`xbl_aop_region@80700000`（1.4 MB）、`pil_spss_region@94000000`（1 MB）、
  `cdsp_secure_heap@94100000`（70 MB）。kebab 的 `PIL Reserved` 到 `0x92400000` 就结束了，本机的
  PIL 区更靠后、更大。这三段只在 Android 的 kernel 里被用（XNU 这个移植不加载 SPSS/CDSP），
  但**如果** UEFI 的 DXE 把 `0x92400000`–`0x9BC00000` 当空闲内存给了别人，就要留意。
- 两处"固定窗口压在保留区上"，是真正要观察的：
  1. `UEFI FD 0x9FC00000 +3 MB` 压住 `kboot_uboot_logmem 0x9FE00000 +2 MB`（OnePlus 自己的 U-Boot 日志）。
  2. `DXE Heap 0xB0000000 +69 MB` 压住 `ramoops 0xB0000000 +4 MB`（Android 的 pstore）。

  两者在 kebab 上也是一样的布局，且都只在"另一边正在运行"时才有意义（UEFI 跑的时候 Android 的
  ramoops 不该被动；HakiOS 从 RAM 启动，不读它）。**所以不改**，只当作首启失败时的第一个检查点：
  如果 UEFI 在写日志/堆时崩，先把 DXE Heap 挪到 `0xB0400000`、大小降到 `0x4100000`。

## 厂商驱动（`Binaries/kebab`）

Mu-Silicium 的 `Binaries` 子模块（HakiOS 的 `uefi/apply.sh` 会 `submodule update --init`）里带着
它支持的机型的厂商 UEFI 驱动，kebab 在里面 —— 所以第一件事是直接编，不必先自己抽。

如果 kebab 的驱动版本与本机 `xbl` 不符（例如显示器不亮、UFS 认不到），再按 HakiOS 的
`uefi/README.md` 从**自己手机的 `xbl` 分区**抽一遍（UEFIReader），放进
`Mu-Silicium/Binaries/kebab/`，本地使用、绝不提交。本机 `xbl_a`/`xbl_b` 在 `sdb1`/`sdc1`，
`xbl_config_a/b` 在 `sdb2`/`sdc2`（`docs/device-report.md` 第 6 节）。

## 本机特有的两个数字（给构建/启动脚本用）

- UEFI FD：base `0x9FC00000`，size `0x300000`（`Resources/Configs/kebab.toml`，与本机
  `kboot_uboot_logmem` 的关系见上）。
- 帧缓冲：`1080x2400x32`（`kebab.dsc` 的 `PcdFrameBuffer*`，与本机 DSI 面板一致）。
