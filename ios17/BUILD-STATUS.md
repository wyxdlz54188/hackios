# 第一次真正编译 iOS 17.0 内核：结果与卡点

2026-11-13，WSL2（Ubuntu，clang 21，theos 工具链，`xnu-10002.1.13` + 本移植的变基补丁）上跑的。
**内核没有编出来**，但已经不是"打不打得上补丁"的问题了：编译进了 900 个编译单元、696 个 `.o`，
卡在两个具体的 iOS 17 新依赖上。

## 环境（都在这台机器上做过一遍）

| 项 | 值 / 做法 |
|---|---|
| WSL | 修复：`LxssManager` 卡 STOP_PENDING，重启后正常；发行版 `Ubuntu` 在 `E:\WSL\Ubuntu` |
| 代理 | Windows 的代理只在 `127.0.0.1:7890`，WSL 到不了；用一个 Node 的 TCP 中继把 `0.0.0.0:7891` 转到它，WSL 里 `https_proxy=http://<网关>:7891` |
| 包 | `build-essential clang lld llvm make cmake git python3 perl flex bison m4 autoconf automake libtool pkg-config libssl-dev zlib1g-dev liblzma-dev libbz2-dev libncurses-dev 7zip lz4 unzip rsync file bc`，**外加 `uuid-dev libelf-dev`**（`SETUP/decomment` 要 `uuid/uuid.h`） |
| theos | `git clone --recursive https://github.com/theos/theos`；Linux 工具链是 `L0ghtmann/llvm-project` 的 `iOSToolchain-x86_64.tar.xz`（`toolchain/linux/iphone/bin/ld` = ld64） |
| SDK | `github.com/theos/sdks` 里最高只有 **iPhoneOS16.5.sdk**（没有 17.0），所以用 16.5 的 SDK 编 17 的内核，`XNU_SDK_VERSION=16.5` |
| xnu-deps | `--stage1` 要拉 6 个仓库（GnuTLS 通过代理常掉，写了个带重试的预取脚本），`--stage2` 要 `RC_DARWIN_KERNEL_VERSION=10002.1.13`（SDK 里的 System.kext 还是 16.5 的版本号，不设就报 "Could not determine xnu version from SDK or KDK"） |
| 配置 | `make oneplus8t_defconfig` 通过（`kernel.ver=2.3.4-hakios-darwin22.5-sm8250`，这里的 darwin22.5 来自公共树的 VERSION 文件，编 17 时应当改成 23.0，见下） |

## 编译到了哪里

```
xnu-build.log: 4663 行, 904 条 CC, 696 个 .o
iokit/DriverKit 的头、MIG 生成、bsd/kern/* 大量文件都过了
```

## 两个卡点（都是 iOS 17 新引入的）

### 1. `<TrustCache/API.h>` 不存在于任何 SDK — 39 个错误

`osfmk/vm/pmap_cs.h`、`bsd/sys/trust_caches.h`、`libkern/libkern/amfi/amfi.h` 都
`#include <TrustCache/API.h>`，而 macOS 13.3 **和 14.5** 的 SDK 里都没有这个头（14.5 只有
`Kernel.framework/Headers/kern/trustcache.h`）；16.5 的 XNU 也不依赖它。它是 Apple 的
`libtrustcache`（闭源）的接口，XNU 17 从它拿 `TrustCache_t`、`TrustCacheRuntime_t`、
`TrustCacheMutableRuntime_t`、`trust_cache_query_token_t`、`trust_cache_runtime_init()` 等。

两条路（还没做）：
- 按 `kern_trustcache.c` 的用法写一个 `TrustCache/API.h` + 最小实现（本移植不校验信任缓存，
  可以让查询一律返回"不在缓存里"）；
- 或者把 `bsd/kern/kern_trustcache.c` 在 `bsd/conf/files` 里改成 `optional`，连同 `pmap_cs` 的
  引用一起关掉，只留一个类型头。

### 2. 新的 DriverKit 类 `IOExtensiblePaniclog` — 需要真正的 iig

XNU 17 新增这个类（16.5 没有），Apple 的 `iig` 是闭源的，HakiOS 用
`xnu-deps/host/bin/iig`（从 macOS SDK 里取同名头 + `iig-impl/` 的空实现）代替。
`IOExtensiblePaniclog.h` 在 13.3 SDK 里没有，我让 shim 从 `.iig` 的 `#if KERNEL #include <IOKit/...>`
生成一个包装头 —— 导出头这一步因此过了，但**内核编译**需要的东西更多：
`iokit/Kernel/IOExtensiblePaniclog.cpp` 里那些 `SetActive_Impl`、`InsertData_Impl`、`CopyMemoryDescriptor_Impl`
是 iig 生成的头里声明的，包装头没有它们，于是 12 个错误。

要做的是把这个类的 iig 输出补出来（按 13.3 SDK 里别的 DriverKit 头的形状：`virtual ... LOCAL;`
加 `_Impl` 声明），或者从 macOS 14 的 SDK 里取 `IOExtensiblePaniclog.h`（如果有）。

## 已经修好的

`osfmk/arm/pmap/pmap.h`：变基后 `struct pmap` 里有两个 `reserved12`（Apple 在 17 里自己加了一个
8 位的，移植的 `#else bool reserved12` 也是一个），179 个错误全是它。17 的 `vm_map.c`、
`vm_dyld_pager.c`、`vm_shared_region.c` 在 `HAS_APPLE_PAC` 之外读 `disable_jop`，所以那个字段
**必须无条件存在**。补丁在 `fixes/pmap.h.patch`（对干净的 `xnu-10002.1.13` 打，替换 pmap.h 的
那一段变基结果）。修完重编：`reserved12` 的错误归零。

## 下一步（按顺序）

1. `TrustCache/API.h`（头 + 最小实现，或关掉 `kern_trustcache.c`）。
2. `IOExtensiblePaniclog` 的 iig 输出。
3. 再编一轮，看剩下的错误（`uipc_mbuf.c`、`bsd/hfs/*` 里也还有几条，`build2.log` 里能看到）。
4. 编过之后才是链接；链接的最后一两步 `check_all_exports` 失败是预期的（公共树的 `make-kernel.sh`
   就是按这个判的）。
5. 公共树 `VERSION` 的 `DARWIN=22.5.0` / `XNU=xnu-8796.121.2` 在编 17 时要改成 `23.0.0` /
   `10002.1.13`，否则内核版本串还是 16.5 的。
