# 编译结果：iOS 17.0.0 内核编出来了

2026-11-13，WSL2（Ubuntu 24.04，clang 21.1.8，theos 的 cctools）上，用 `xnu-10002.1.13` + 本移植的
变基补丁，**链接出了一个 arm64 Mach-O 内核**：

```
mach.development.bcm2837   15 067 968 字节
Mach-O 64-bit arm64 executable, flags:<NOUNDEFS|PIE>
sha256  e6b79530aad539af586d64aec9a80f52780416969000f5339013b78ddf53b5de
```

公共树的 `tools/make-kernel.sh --judge` 判定为成功：

```
make-kernel: the log shows a built kernel; only the kext symbol-set checks failed
```

（最后失败的 `config_all` / `check_all_exports` 是这个手机配置本来就有的：没有 DriverKit 与 Apple
silicon 的那些 kext 符号。上游就是这么判的。）

**没有上机**：这个内核还没进 `hakios-kernel`、没做 boot image、没碰过手机。

## 从 251 个错误到一个内核：修了什么

补丁已经把这些全部包含：`ios17/hakios-xnu-10002.1.13.patch`（3.7 MB，208 段，在干净的
`xnu-10002.1.13` 上 `git apply --check` 通过）。逐条：

| # | 现象 | 原因 | 修法 |
|---|---|---|---|
| 1 | `pmap.h: duplicate member 'reserved12'`（179 个错误） | 17 自己加了一个 `uint8_t reserved12`，移植的 `#else bool reserved12` 又加一个；17 还在 `HAS_APPLE_PAC` 之外读 `disable_jop` | `disable_jop` 无条件保留，删掉那个 `#else` |
| 2 | `<TrustCache/API.h> file not found`（39 个） | XNU 17 依赖 Apple 闭源 libTrustCache 的接口，任何 SDK（13.3、14.5 都查过）都没有这个头 | `EXTERNAL_HEADERS/TrustCache/API.h`：按树里的用法（pmap_cs.h、amfi.h、miniamfi.c、kern_trustcache.c）重建类型与常量；`trustCacheInitializeRuntime()` 做成空实现；`TCTypeConfig[]` 全为 NULL（本移植不校验信任缓存） |
| 3 | `IOExtensiblePaniclog` 的 12 个错误 | 17 新增的 DriverKit 类，`iig` 是闭源的 | 从 **macOS 14.5 SDK** 取真正的 `DriverKit/*.h`（35 个头）放进 13.3 SDK；再把这个类的 `.cpp` 与 `.iig.cpp` 从 `iokit/conf/files` 里关掉（本移植没有 paniclog-to-userspace 这条路） |
| 4 | `nspace_snapshot_event` / `resolve_nspace_item` 未声明（13 个） | XNU 17 不再提供这两个函数，Apple 的 HFS（hfs-627.100.6）还在调 | `bsd/hfs/hfs.h` 里加两个 inline 空实现（无 namespace handler，返回 0） |
| 5 | `kern_exec.c`: `kauth_cred_setresuid` 不存在 | 17 删掉了直接改真实凭据的 setter，只剩 model 版 | persona 兜底改成 no-op + `ios17 TODO(port)`：**这是行为退让**，Sileo 的 apt/dpkg 会以 mobile 身份跑，要按 17 的 API 重做 |
| 6 | `percpu.h`: `expected expression` | 变基时宏的续行被合坏（`; \        \`） | 重写 `percpu_foreach_secondary` |
| 7 | 链接：`_memcpy`、`_memmove`、`_ovbcopy` 未定义 | `osfmk/conf/files.arm64` 第 29 行把 amcc 的注释和 `osfmk/arm64/bcopy.s standard` 粘成了一行，`bcopy.s` 从没编过 | 拆成两行；`bcopy.s` 进去之后三个符号都有了 |

## 环境（复现用）

| 项 | 值 |
|---|---|
| 系统 | WSL2 Ubuntu，`/home/sean/hakios`（公共树 + `devices/oneplus8t`） |
| 编译器 | clang 21.1.8、lld（`ld64.lld`）、GNU make 4.4.1 |
| 工具链 | theos（`toolchain/linux/iphone/bin/ld`）+ `theos/sdks/iPhoneOS16.5.sdk`（**这个 SDK 没有 17.0**） |
| 依赖 | `uuid-dev libelf-dev`（`SETUP/decomment` 要 `uuid/uuid.h`） |
| xnu-deps | stage1 + `RC_DARWIN_KERNEL_VERSION=10002.1.13` 的 stage2；`MacOSX13.3.sdk`（DriverKit 头）+ 从 14.5 SDK 补的那 35 个头 |
| iig | `xnu-deps/host/bin/iig` 给 17 新增的类生成 `#if KERNEL #include <IOKit/...>` 包装头 |
| 配置 | `make oneplus8t_defconfig`（含 `open.config`）；`XNU_SDK_VERSION=16.5` |
| 构建 | `./xnu-build.sh -k -j4`，1585 行日志、937 个目标文件、kernel 15 MB |

代理：Windows 的代理只听 `127.0.0.1:7890`，WSL 到不了；用一个 Node TCP 中继（`0.0.0.0:7891`）转进去。

## 下一步

1. **上机**：`cp .../mach.development.bcm2837 ~/hakios/hakios-kernel`，然后 `./xl enter`（UEFI 用
   Mu-Silicium 现成的 kebab 平台，见 `uefi/README.md`）。首启大概率停在 UEFI/loader 或早期内核，
   日志在 `logs/`。
2. 把 persona 兜底按 17 的 `kauth_cred_model_setuidgid()` 重做（第 5 条）。
3. 驱动逐个打开（`docs/port-checklist.md` 第 3 步）。
4. `RC_DARWIN_KERNEL_VERSION` 与公共树 `VERSION` 的 `DARWIN=22.5.0`/`XNU=8796` 应当改成 23.0/10002，
   否则版本串还是 16.5 的。
