# fixes/ — 变基之后、编译之前要打的补丁

`ios17/hakios-xnu-10002.1.13.patch` 是把 16.5 的移植变基到 `xnu-10002.1.13` 的结果。它是**逐 hunk
合并**出来的，编译器随后指出了几处合并对了语法、合并错了语义的地方。这里放这些修正。

| 文件 | 是什么 | 怎么用 |
|---|---|---|
| `pmap.h.patch` | `struct pmap` 里的两个 `reserved12`：17 自己加了一个 `uint8_t reserved12`，移植的 `#else bool reserved12` 又加一个。17 的 `vm_map.c`/`vm_dyld_pager.c`/`vm_shared_region.c` 在 `HAS_APPLE_PAC` 之外读 `disable_jop`，所以这个字段要无条件存在。里面还带着移植原有的 `BOOTSTRAP_TABLE_SIZE` 那一 hunk（那是 16.5 移植的一部分，不是这次修的） | 在 `ios17/apply.sh` 建出的树上：`git apply fixes/pmap.h.patch`，或者按它改；**或者**把它合进 `hakios-xnu-10002.1.13.patch` 里 pmap.h 的那一段，以后就不必单独打 |

## 不在这里、但环境要有的两处（见 `BUILD-STATUS.md`）

- `xnu-deps/host/bin/iig`：给 iOS 17 新增的 DriverKit 类生成 `#if KERNEL #include <IOKit/...>` 的包装头，
  否则 `exporthdrs` 在 `IOExtensiblePaniclog` 上停住。包装头只够导出，**不够编译** —— 还缺 iig 生成的
  类声明（`*_Impl` 方法），这是 `BUILD-STATUS.md` 的卡点 2。
- `xnu-deps/setup.sh --stage2` 要 `RC_DARWIN_KERNEL_VERSION=10002.1.13`，因为 SDK overlay 还是
  16.5 的 System.kext。
