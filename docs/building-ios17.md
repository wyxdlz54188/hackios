# 编译 iOS 17.0.0 内核：WSL 里怎么搭起来

这份文档只讲"把内核编出来"（`hakios-kernel`）。iPhone 用户态、UEFI 镜像、驱动是另外的步骤
（见 `docs/port-checklist.md`）。命令都是在 **WSL 的 Linux 里、在公共仓库的根目录**下执行的。

## 0. 这台机器现在的状态：WSL 卡住了

诊断结果（2026-11-13）：

```
sc query LxssManager  ->  STATE : 3  STOP_PENDING
```

`LxssManager`（WSL 的服务）停在 STOP_PENDING，所以**任何** `wsl.exe` 调用都会挂住（`wsl --status`
也一样），这不是发行版的问题。恢复顺序，从轻到重：

```powershell
# 1) 先试不需要重启的（通常就够了）
wsl --shutdown
Restart-Service LxssManager        # 管理员 PowerShell
sc query LxssManager               # 要看到 RUNNING

# 2) 还卡着：结束宿主进程再拉起服务（netsvcs 组会短暂受影响，可能断一下网）
Get-CimInstance Win32_Service -Filter "Name='LxssManager'" | Select-Object ProcessId
taskkill /f /pid <上面的 ProcessId>
sc start LxssManager

# 3) 最稳：重启。重启后 wsl -l -v 应当立刻返回
```

修好后先验一下（应当 1 秒内返回）：

```powershell
wsl -l -v
```

```
  NAME      STATE           VERSION
* Ubuntu    Running         2
```

> 本机的发行版在 `E:\WSL\Ubuntu`（注册表 `HKCU\Software\Microsoft\Windows\CurrentVersion\Lxss`，
> 名字 `Ubuntu`，WSL2）。它还在，只是服务卡住。

## 1. 机器要求

| 项 | 要求 | 为什么 |
|---|---|---|
| 发行版 | Ubuntu 22.04 或 24.04（WSL2） | theos 的 Linux 工具链与 clang 版本 |
| 内存 | ≥ 12 GB 给 WSL（`~/.wslconfig` 里 `memory=12GB`） | XNU 的 make -j8 很吃内存 |
| 磁盘 | ≥ 40 GB 空闲，**在 WSL 自己的文件系统里** | 见下面"别在 /mnt/e 里编" |
| 核数 | 8 左右 | `-j8` |

`~/.wslconfig`（Windows 用户目录）示例：

```ini
[wsl2]
memory=12GB
processors=8
swap=8GB
```

**别在 `/mnt/e` 里编**：XNU 的构建产物里有 `NAME:com.apple.decmpfs` 这种带冒号的文件名，NTFS 不允许；
而且几万个小文件走 9p 会慢到无法忍受。正确做法是把仓库放在 `~/hakios`（WSL 自己的 ext4），
编完再把 `hakios-kernel` 拷回 Windows。

## 2. 依赖包

```sh
sudo apt update
sudo apt install -y build-essential clang lld llvm make cmake git curl wget \
  python3 python3-pip perl flex bison m4 autoconf automake libtool pkg-config \
  libssl-dev zlib1g-dev liblzma-dev xz-utils libbz2-dev libncurses-dev \
  7zip lz4 unzip rsync file bc
clang --version     # Ubuntu 22.04 是 14，24.04 是 18：都能编，18 更接近 Apple 的
```

`xnu-deps/setup.sh` 还要 `mig`、`unifdef`、`tcsh`、`csh` —— 这些**不用**装，脚本自己编
（源码在 `xnu-deps/` 里拉）。但 `flex/bison/m4/perl` 必须是系统的。

## 3. theos 与 iOS 17.0 的 SDK

XNU 的链接用 theos 的 cctools（`ld64`），内核头文件用 theos 的 Darwin SDK。

```sh
export THEOS=$HOME/theos
git clone --recursive https://github.com/theos/theos.git "$THEOS"
# Linux 的工具链（cctools）：按 https://theos.dev/docs/installation-linux 装，
# 或者在 macOS 上 `make package` 一次把 toolchain/linux/iphone 带过来
ls "$THEOS/toolchain/linux/iphone/bin/ld"     # 必须有：链接内核用它
```

SDK：theos 不自带 Apple 的 SDK。iOS 16.5 时代从 `github.com/theos/sdks` 拿
`iPhoneOS16.5.sdk`；**17.0 要么从 Xcode 15 的
`Xcode.app/Contents/Developer/Platforms/iPhoneOS.platform/Developer/SDKs/iPhoneOS17.0.sdk`
拷出来，要么用 `github.com/theos/sdks` 里有的最近版本**（内核只用到 SDK 的头文件与 tbd，
版本差一点通常能编，但 `xnu-env.sh` 的 `XNU_SDK_VERSION` 要跟着改）。

```sh
ls "$THEOS/sdks"          # 期望看到 iPhoneOS17.0.sdk（或你实际有的那个）
```

公共仓库的 `xnu-env.sh` / `xnu-deps/setup.sh` 把 16.5 写死了（`DARWIN_SDK`、`XNU_SDK_PATH`、
`XNU_SDK_VERSION`）。编 17.0 时把这几处指向 17：

```sh
cd ~/hakios
sed -i 's/iPhoneOS16\.5\.sdk/iPhoneOS17.0.sdk/g; s/iPhoneOS16\.5\.xnu\.sdk/iPhoneOS17.0.xnu.sdk/g; s/XNU_SDK_VERSION=16\.5/XNU_SDK_VERSION=17.0/' \
    xnu-env.sh xnu-deps/setup.sh
```

（改的是公共仓库的两个脚本；这些都是"名字"，编 17 的树就该用 17 的名字。）

## 4. 建树：用 iOS 17 的 XNU，而不是 16.5 的

```sh
cd ~/hakios
cp -a /mnt/e/HackIOS devices/oneplus8t        # 或者 git clone 过来
make oneplus8t_defconfig

# 17.0 的内核树（这一步会拉 xnu-10002.1.13 并打补丁，约 3 分钟）
HAKIOS=$PWD devices/oneplus8t/ios17/apply.sh
# -> xnu-src/xnu-10002.1.13/，分支 hakios17
```

`apply.sh` 会把 `config/MASTER.hakios`、`bsd/dev/hakios.drivers.h` 一起生成（它调用
`tools/hakios-config.py kernel`），并把 HFS Plus 放进去。缺什么它会明说。

## 5. 依赖库与 SDK overlay

```sh
xnu-deps/setup.sh --stage1      # 拉 Apple 的开放源 + 编 mig/unifdef/tcsh + 做 sdk/iPhoneOS17.0.xnu.sdk
xnu-deps/setup.sh --stage2      # 两个链接到内核导出头的静态库（需要第 4 步的树）
# 改过内核头文件之后：
xnu-deps/setup.sh --rebuild-libs
```

`--stage1` 里的 `MacOSX13.3.sdk`（只取 `Kernel.framework` 的 DriverKit 头）与 `iig` 的桩在
`xnu-deps/iig-impl/`，这两个是 XNU 17 也能用的（Apple 的 `iig` 是闭源的，桩来自链接器未定义符号）。

## 6. 编

```sh
export XNU_SRC=$PWD/xnu-src/xnu-10002.1.13
export XNU_SDK_PATH=$PWD/xnu-deps/sdk/iPhoneOS17.0.xnu.sdk
export XNU_SDK_VERSION=17.0
KERNEL=xnu-src/xnu-10002.1.13/BUILD/obj/DEVELOPMENT_ARM64_BCM2837/mach.development.bcm2837 \
  tools/make-kernel.sh -j8
```

或者用本仓库的封装（它把上面这些变量都设好，并先跑 `tools/check-ios17-tree.py`）：

```sh
devices/oneplus8t/tools/build-ios17.sh -j8
```

**退出码 2 是正常的**：XNU 最后几步做 kext 的 symbol set 与 `check_all_exports`，这个手机配置本来就没有
DriverKit / Apple silicon 的那些符号。`tools/make-kernel.sh` 正是按"哪些目标失败了"判断的：只有那几步
失败、且 `mach.development.bcm2837` 在，就算成功，并把它复制成 `hakios-kernel`。

**第一次编一定会出错**，这是重点，不是意外：150 多个驱动对 17.0 的编译没人验证过。把日志留下来：

```sh
grep -nE '(error|fatal error):' xnu-build.log | head -40
```

按 `ios17/REBASE.md` 的"还没做的"逐条处理；每修一处，`ios17/REBASE.md` 里补一行。

## 7. 编出来之后

```sh
ls -l hakios-kernel
cp hakios-kernel /mnt/e/HackIOS/prebuilt/            # 想留在 Windows 侧的话
```

然后才能在手机上跑（`./xl enter`、`make phone`），见公共仓库的 `docs/getting-started/phone.md`。

## 8. 实测记录（2026-11-13，这台机器）

第一次真编的结果与卡点写在 `ios17/BUILD-STATUS.md`。和上面几节不同的地方，都是实测出来的：

| 上面写的 | 实测要这样 |
|---|---|
| `sudo apt install ...` | 还要 **`uuid-dev libelf-dev`**：`SETUP/decomment` 要 `uuid/uuid.h` |
| theos 的 `sdks/iPhoneOS17.0.sdk` | **`github.com/theos/sdks` 没有 17.0**，最高 16.5；先用 16.5 的 SDK 编 17 的内核（`XNU_SDK_VERSION=16.5`），`xnu-env.sh` 的名字也就不用改 |
| `xnu-deps/setup.sh --stage1` | 它会拉 6 个 git 仓库，走代理时 GnuTLS 常掉；先带重试地预取一遍（`xnu-deps/<name>` 有 git HEAD 它就会跳过） |
| `xnu-deps/setup.sh --stage2` | 要 `RC_DARWIN_KERNEL_VERSION=10002.1.13`，否则 "Could not determine xnu version from SDK or KDK" |
| iig | 17 新增的 DriverKit 类（`IOExtensiblePaniclog`）不在 13.3 SDK 里，`xnu-deps/host/bin/iig` 要让它从 `.iig` 生成包装头（`fixes/README.md`） |

网络上的一个办法：Windows 的代理只听 `127.0.0.1`，WSL 到不了。用一个 TCP 中继把
`0.0.0.0:7891` 转到 `127.0.0.1:7890`（Node 二十行），WSL 里
`export https_proxy=http://$(ip route show default | awk '{print $3}'):7891`，git 与 curl 就都通了。

```sh
# 编之前先体检
HAKIOS=$PWD devices/oneplus8t/tools/build-ios17.sh --check
```

