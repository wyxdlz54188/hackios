# HakiOS 移植：OnePlus 8T (KB2000 / instantnoodle / SM8250 "kona") — 目标 iOS 17.0.0

这个目录是一份 **HakiOS 设备移植仓库**（结构对标 `hakios-sm7325`），并且把内核目标从上游的
iOS 16.5（`xnu-8796.121.2`, Darwin 22.5.0）**推进到 iOS 17.0.0（`xnu-10002.1.13`, Darwin 23.0.0）**。

所有设备数据都是从这台真机（`adb` + root，序列号 `c8646380`）上读出来的，不是猜的；
每个数字的来源写在 `docs/device-report.md` 里。临时文件与实验树都在工作区
`E:\Deepseek\_work\`，不在这里。

## 现在是什么状态

| 部分 | 状态 | 说明 |
|---|---|---|
| 设备移植骨架（`device.conf`、`configs/`、`soc/`、`soc.args`） | **done** | 按上游工具与格式写成，`tools/check-port.py` 通过 |
| 设备数据（DT、分区、固件、内存映射） | **done** | `docs/device-report.md`，真机只读采集 |
| iOS 17.0.0 内核层（8796 → 10002 变基） | **partial** | 203 个文件、46 处冲突全部处理完并提交：`ios17/hakios-xnu-10002.1.13.patch`；**尚未编译过**（见下） |
| 编译与启动 | **missing** | 需要 Linux + clang + theos SDK；本机是 Windows，只做到补丁层面 |
| 各硬件驱动（显示/触摸/UFS/GPU/Wi-Fi/音频/基带…） | **missing** | 上游驱动全是参考机（redwood/sc7280）的地址与芯片；逐项待写，见 `docs/port-checklist.md` |
| UEFI | **partial** | **不用新写平台**：Mu-Silicium 已带 `kebabPkg`，而 kebab 就是这块板。已做内存映射比对（`docs/uefi-map-report.md`）；未构建、未启动，见 `uefi/README.md` |

> 结论先说清楚：**现在还不能开机进 iOS 17**。内核"补丁层"的 17.0 变基是真的做完了（可复现），
> 但没有编译环境、没有 UEFI 平台、没有一个 kona 驱动，所以"能启动"这一条不成立。
> 上游自己的 redwood 也是逐个驱动做出来的，顺序见 `docs/port-checklist.md`。

## 怎么用（在 Linux/WSL 里，配合上游公共仓库）

```sh
# 1. 取上游公共仓库（内核移植、驱动、loader、工具）
git clone --depth 1 https://github.com/oosexgang/hakios-xnu-kernel hakios
cd hakios

# 2. 把这个设备仓库放进去（或加进 devices/manifest.conf）
git clone <this-repo> devices/oneplus8t
make oneplus8t_defconfig
make config                     # 检查配置与 boot-args 是否自洽

# 3. iOS 17.0.0 的内核：用本仓库 ios17/ 的补丁，而不是上游的 hakios.patch
ios17/apply.sh                  # = 拉 xnu-10002.1.13 + 打补丁 -> xnu-src/xnu-10002.1.13/（git 分支 hakios17）

# 4. 用户态（iOS 17.0.0 的 IPSW，A12 及以上的机型）
sysimage/unpack.sh /path/to/iPhone11,2_17.0.0_21A329_Restore.ipsw   # 需改 unpack.sh 里的成员名/大小
```

## 为什么 iOS 17 的补丁要单独维护

上游 `xnu/hakios.patch` 是针对 `xnu-8796.121.2` 写的。17.0.0 的 XNU 是 `xnu-10002.1.13`，
Apple 在 BSD/VFS、pmap、调度、persona、jetsam 上都动了。`ios17/REBASE.md` 记录了这次变基的
**每一处冲突和取舍**，`ios17/apply.sh` 可以一键复现同样的树。

## 目录

| 路径 | 内容 |
|---|---|
| `device.conf` | 这台设备的身份与各部件状态（HakiOS 的唯一状态来源） |
| `configs/oneplus8t_defconfig`, `configs/oneplus8t.config` | 设备层配置（common + SoC + 本机） |
| `soc/` | SM8250 (kona) 的 SoC 层：`soc.conf`、`configs/sm8250.config` |
| `soc.args` | 从本机 DT 读出的 modem/IPA/SMEM 地址，`tools/soc-args-kona.py` 生成 |
| `ios17/` | iOS 17.0.0 目标：版本钉死、变基报告、补丁、复现脚本 |
| `uefi/` | UEFI 这边：本机为什么是 Mu-Silicium 的 kebab、怎么建、内存映射比对的结论 |
| `docs/` | 真机数据报告、移植清单（按上游的驱动顺序） |
| `tools/` | 只读采集、kona 版 soc-args、仓库自检 |
| `prebuilt/device-tree.dtb` | 本机 `/sys/firmware/fdt`（787 882 字节），soc.args 的来源 |

## 来源与许可

上游 HakiOS：<https://github.com/oosexgang/hakios-xnu-kernel>（XNU 派生物 APSL-2.0，其余 MIT）。
本仓库自己的文件（docs、tools、configs、soc、uefi、脚本）是 MIT，见 `LICENSE`；
`ios17/hakios-xnu-10002.1.13.patch` 是 XNU 的派生作品，APSL-2.0，见 `LICENSE.APSL`；
第三方与"什么不在这里"见 `NOTICE`。`prebuilt/device-tree.dtb` 是这台手机自己的设备树，
不含任何 Apple 或厂商固件。厂商固件永远不进仓库（`pull-firmware.sh` 自己拉）。
