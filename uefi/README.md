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

### 二分的第一个结果（2026-11-13 傍晚）

`xnu-hakios-nopayload-v1dtb.img`（**只有 UEFI，没有 loader**）被 ABL 接受，然后：

```
t=1  fastboot 设备出现，序列号 ????????????   <- UEFI 的 USB 栈起来了
t=2  消失
t=3  900E，屏幕全黑
```

结论：ABL→镜像的交接没问题（boot.img 格式、FD 基址、BootShim 都不再是嫌疑）；**崩在 UEFI 里**，
USB 初始化之后约 3 秒，还没到显示初始化（所以黑屏），loader 根本没参与。

下一步只剩一个不编译的对照：把第一份镜像里的**原版 Mu-Silicium FD** 抽出来（`dd` + `gunzip` +
`mkbootimg` 重新打包，不编译），做一个"原版 UEFI、无 payload"的镜像 —— 若它也崩，是这个 kebab 平台
在这台 12 GB 的 KB2000 上不行；若它活着，则是 HakiOS 的 BootManager/loader 补丁崩的。

### 根因（读源码读出来的，2026-11-13）

黑屏 + 900E 的原因在 HakiOS 自己的 stage-0 loader（`Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/XnuLoader.c`）：

```c
STATIC VOID StartPayloadLoader (VOID) {
  XNU_PAYLOAD_HEADER *Header = (XNU_PAYLOAD_HEADER *)XNU_PAYLOAD_BASE;   // 0xF0000000
  ...
  if (AsciiStrnCmp (Entry->Name, "loader.efi", sizeof (Entry->Name)) == 0) { ... }
}
```

两处：

1. **payload 的条目名必须是 `loader.efi`**。我们的镜像里是 `loader=`（`mkpayload.py loader=xnuloader/loader.efi`），
   名字对不上 → UEFI **不会启动真正的 loader**，直接掉进 stage-0 的诊断路径。
2. 诊断路径里 `LogPayload()` 无条件读 `*(0xF0000000)`，`LogPersistence()` 还写到
   `0xF0000000 + 4 MB - 4 KB`。这台手机在这个窗口没有映射内存（HakiOS 自己的注释也写了 IMEM/watchdog
   的 MMIO 读会触发同步异常）→ **同步异常 → 900E**。所以「不带 payload 的那次」必崩；「带 payload 但名字错」
   的那次也会走到同一个坑里。屏幕全黑是因为 stage-0 故意不显示任何东西（它只往 `logdump` 分区写日志）。

修法（`uefi/fixes/`）：

- `xnuloader-payload-window.diff`：给 `XnuLoader.c` 加 `PayloadWindowMapped()`（查
  `GetMemoryMap`），`LogPayload`/`LogPersistence`/`StartPayloadLoader` 在碰这块内存之前先问它；
  没有 payload 就记一句然后照常复位，不再崩。
- `uefi/mkimg.py`：自己构造 XNUP payload，条目名固定 `loader.efi`；用外部 `--payload` 时也检查
  第一个条目名，不是 `loader.efi` 就拒绝打包。

**已落地（2026-11-13 第二轮）**：修复以**设备仓库覆盖层**的形式进本仓库
`uefi/files/Silicon/Silicium/SiliciumPkg/Library/BootManagerLib/XnuLoader.c` —— 公共树的
`uefi/apply.sh` 在拷贝 `hakios-uefi/files/` **之后**才拷 `devices/<name>/uefi/files/`，所以重建
树时我们的版本覆盖上游那份。带修复的 FD 已重编出来（`Build/kebabPkg/RELEASE_CLANGPDB/FV/
SILICIUM_UEFI.fd`，3 145 728 字节），`uefi/mkimg.py` 重打的 `xnu-oneplus8t.img`（1 802 240 字节）
payload 第一个条目就是 `loader.efi`。

**重建环境的四个坑**（都在 WSL 的 `/home/sean/mu3`，树 = BASE `e51cd87` + `hakios.patch` + 两个
覆盖层）：

1. `Silicon/Silicium/OpensslPkg/.../openssl` 子模块 pin 的 commit（`67b5686`）上游已消失，
   `stuart setup/update` 永远失败；kebab 不用 OpensslLib，所以覆盖层
   `uefi/files/Platforms/OnePlus/kebabPkg/DeviceBuild.py` 把这个 RequiredSubmodule 删了
   （diff 在 `uefi/fixes/kebab-devicebuild-submodules.diff`），Mu_Basecore 也改成
   非递归（它嵌套的 libspdm pin 的 openssl/mbedtls commit 同样没了）。
2. BaseTools 不要等 `Mu-Basetools` 下载（WSL 出不了网）：`make -C Mu_Basecore/BaseTools`
   从源码编（309 个测试全过），跑构建时
   `PATH=Mu_Basecore/BaseTools/BinWrappers/PosixLike:$PATH`。
3. `nasm`/`onecrypto` 两个 ext_dep 描述符（`BaseTools/Bin/*_ext_dep.yaml`、
   `CryptoPkg/Binaries/OneCrypto_ext_dep.json`）抓不下来会把 update 判成 ERROR —— 挪走即可，
   kebab 的 AARCH64 构建两个都不需要；iasl 是 `cibuild` scope，本来就不会抓。
4. `build_uefi.py` 在 `Build/` 目录已存在时**跳过** setup/update —— 所以被 1–3 搞干净后，
   重跑 `python3 build_uefi.py -d kebab -r RELEASE` 直接就编译，约 2 分钟出 FD。

WSL 出网走 Windows 主机的代理：`export https_proxy=http://192.168.1.5:7890 http_proxy=http://192.168.1.5:7890`
（`192.168.1.5` 是 Windows 在局域网里的地址；代理只听 Windows 侧，所以 WSL 里不能用 127.0.0.1）。
有了它第 2、3 条可以改成正常下载（把挪走的描述符放回即可），但第 1 条的 openssl pin 是上游真删了，
代理也拉不回来 —— DeviceBuild.py 覆盖层仍然必需。

**下一步（只差手机）**：手机完整重启一次清掉 ABL 的 Load Error 状态，然后
`fastboot boot xnu-oneplus8t.img`。期望看到 HakiOS logo 或至少 loader 的日志路径；若还进 900E，
按上面"二分"一节的顺序排查。

### 二分的第二个结果：崩在 XnuLoaderMain 之前（2026-11-13 晚）

修好 `PayloadWindowMapped()` + payload 条目名 `loader.efi` + 进度标记之后重新编译、上机：

- **带 loader 的镜像**：`Booting OKAY` → `????????????` 的 fastboot 出现 1 秒 → 900E，黑屏。
- **不带 payload 的镜像**（关键对照）：也 900E，黑屏。
- 回 Android 读 `logdump` 分区：**没有任何标记/日志**（只有 `ff fe` 头 + 全零）。

结论（按"分区全零 → loader 没跑起来"的判据）：**崩溃发生在 UEFI 的 DXE 启动阶段、XnuLoaderMain 之前**，
即 Mu-Silicium 的 kebab 平台在这台机器上还没走到启动管理器就崩了（黑屏 = 显示从没初始化）。原版
Mu-Silicium 也一样崩，所以**不是 HakiOS 的补丁/loader 的问题**，是平台与本机不匹配。

设备身份（从 `prebuilt/device-tree.dtb` 读的）：`model = kona MTP 19805`、`oplus,dtsi_no = 0x4d5d (19805)`、
`qcom,board-id = 1, 8`。`19805` 是 OnePlus 项目号（8T = kebab 家族），但 Mu-Silicium 的 kebab 平台是以
某个特定内存/DDR/面板的 8T 为基准的；这台 12 GB 的 KB2000 疑似在 DDR/显示/内存映射上有差异，导致某个
厂商 DXE 驱动在启动早期就 fault。

**下一步要换工具**（盲试到此为止，需要一个能"看见早期崩溃"的手段）：

1. 给 Mu-Silicium 的 **Sec/最早的 DXE 驱动** 加标记（往固定物理地址或 UFS 写字节），把二分往下再推一层；
2. 或者上 **串口/UART**（kona UART `0xa90000`，需要拆机引线）；
3. 或者查 Mu-Silicium 对 **KB2000 / 12 GB** 的已知问题、换一个更接近本机的平台包。

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
