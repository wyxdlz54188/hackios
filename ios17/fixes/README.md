# fixes/ — 变基之后到"编得出来"之间的修正

`ios17/hakios-xnu-10002.1.13.patch` 是 16.5 的移植变基到 `xnu-10002.1.13` 的结果，**现在已经包含**
下面这些修正（在干净的 `xnu-10002.1.13` 上 `git apply --check` 通过，编出了 arm64 内核）。
这里保留两样东西，作为"为什么"：

| 文件 | 是什么 |
|---|---|
| `TrustCache-API.h` | XNU 17 依赖、而任何 SDK 都没有的 `<TrustCache/API.h>`，按树里的用法重建（补丁里已放在 `EXTERNAL_HEADERS/TrustCache/API.h`）。单独留一份，是为了以后 Apple 放出真头时对照 |
| `README.md` | 这个文件 |

每条修正的原因、现象与修法在 `../BUILD-STATUS.md` 的表里；`pmap.h`、`files.arm64`、`percpu.h`、
`hfs.h`、`kern_exec.c`、`iokit/conf/files` 的改动都已经在补丁里了。

## 不在补丁里、属于环境的

- **macOS 14.5 SDK 的 `DriverKit/*.h`（35 个）**：XNU 17 新增的 DriverKit 类（`IOExtensiblePaniclog`）
  不在 13.3 SDK 里，从 14.5 的 `Kernel.framework/Headers/DriverKit/` 拷进 13.3 SDK。
- **`xnu-deps/host/bin/iig`**：给没有预生成头的类，从 `.iig` 的 `#if KERNEL #include <IOKit/...>`
  生成包装头。
- **`RC_DARWIN_KERNEL_VERSION=10002.1.13`**：SDK overlay 的 System.kext 还是 16.5 的版本号。
