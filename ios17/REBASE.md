# 变基报告：HakiOS 16.5 的内核工作 → `xnu-10002.1.13`（iOS 17.0.0）

**做了什么**：把上游 `xnu/hakios.patch`（针对 `xnu-8796.121.2`，iOS 16.5）连同 `xnu/files/`、`drivers/`
一起，三段式变基到 `xnu-10002.1.13`（Darwin 23.0.0，iOS 17.0.0）上，产出
`hakios-xnu-10002.1.13.patch`。

**结论**：补丁层**做完了**（可复现，46 处冲突全部有记录、有取舍，且在干净的 10002 树上
`git apply --check` 通过）；**没有编译过**，也没有在手机上跑过。"能启动"这一条不成立。

| 数字 | 值 |
|---|---|
| 源补丁 | `hakios.patch` 137 181 字节，82 个 Apple 文件 |
| 上游新增文件 | `xnu/files/` 72 个 + `drivers/map` 49 个 |
| 直接 `git apply --reject` 到 10002 | **23 个文件**留下 `.rej`（清单见第三节） |
| 三段式变基（`git rebase --onto`） | **18 个文件、46 处冲突** |
| 其中机械冲突（同一修复，17 已自带） | **37 处 / 13 个文件** |
| 其中需要判断的语义冲突 | **9 处 / 5 个文件** |
| 变基后补丁 | 203 个文件（82 改 + 121 新增），84 745 行插入、190 行删除，3.7 MB |
| 变基后的树 | `xnu-10002.1.13` + 一个提交（`hakios16` 分支） |
| 验证 | 在 `xnu-10002.1.13` 的干净树上 `git apply --check` **通过** |

> 为什么"直接 apply 剩 23 个文件"比"变基剩 18 个文件"更糟：`git apply` 是逐块贴，上下文一变就整块放弃；
> `git rebase` 是三次合并，只有两边都改了同一段才冲突。所以正式产物用变基这条路的。

## 怎么复现

```sh
# 1. 两个 tag 与苹果的源
git init xnu && cd xnu
git remote add origin https://github.com/apple-oss-distributions/xnu.git
git fetch --depth 1 origin refs/tags/xnu-8796.121.2:refs/tags/xnu-8796.121.2
git fetch --depth 1 origin refs/tags/xnu-10002.1.13:refs/tags/xnu-10002.1.13

# 2. 把 16.5 的工作做成一个提交（patch + files/ + drivers/map），分支 hakios16
git checkout -b hakios16 xnu-8796.121.2
git apply --whitespace=nowarn /path/to/hakios/xnu/hakios.patch
cp -a /path/to/hakios/xnu/files/. .
while read -r sub tree _; do case "$sub" in ''|'#'*) continue;; esac
  cp /path/to/hakios/drivers/$sub/$(basename $tree) $tree; done < /path/to/hakios/drivers/map
git add -A && git commit -m "hakios: iOS 16.5 work"

# 3. 变基到 17.0 的 tag
git rebase --onto xnu-10002.1.13 xnu-8796.121.2 hakios16      # 46 处冲突

# 4. 产出补丁
git diff xnu-10002.1.13 hakios16 > hakios-xnu-10002.1.13.patch
```

本仓库 `ios17/apply.sh` 消费的是第 4 步的产物：拉 tag、`git apply` 一个补丁。

## 一、13 个文件、37 处：机械冲突（取 17 的）

16.5 的移植给 XNU 加过一个宏 `UIO_STACKBUF(name, niov)`，因为 Apple 原来的
`uio_stackbuf_t uio_buf[N]` 写法（`char` 数组的过度对齐）在 clang 16+ 上被拒绝。**17.0 自己修了同一个问题**，
用的是 `typedef uint64_t uio_stackbuf_t;` + 每个调用点展开成
`uio_stackbuf_t uio_buf[(UIO_SIZEOF(n) + sizeof(uio_stackbuf_t) - 1) / sizeof(uio_stackbuf_t)]`。

于是这 37 处一律取 17 的写法，`bsd/sys/uio_internal.h` 里的 `UIO_STACKBUF` 宏整段删掉：

| 文件 | 处数 |
|---|---|
| `bsd/vfs/vfs_syscalls.c` | 10 |
| `bsd/nfs/nfs_serv.c` | 5 |
| `bsd/vfs/vfs_attrlist.c` | 5 |
| `bsd/kern/sys_generic.c` | 4 |
| `bsd/vfs/vfs_quota.c` | 4 |
| `security/mac_vfs_subr.c` | 2 |
| `bsd/kern/decmpfs.c`、`bsd/kern/kpi_socket.c`、`bsd/kern/uipc_syscalls.c`、`bsd/sys/uio_internal.h`、`bsd/vfs/vfs_lookup.c`、`bsd/vfs/vfs_subr.c`、`bsd/vfs/vfs_vnops.c` | 各 1 |

`bsd/nfs/nfs_serv.c` 里有一处不是一行换一行（旧的 `void *uio_bufp = &uio_buf[0]` 要跟着改成
`char *uio_bufp` 和 `UIO_SIZEOF(4)`），取 17 的整段即可，因为两边算的是同一个大小。

## 二、5 个文件、9 处：要判断的

### 1. `bsd/kern/kern_exec.c` —— `spawn_persona_adopt()`：17 换了 API，保留移植的兜底

- 16.5：`persona_proc_adopt(p, persona, cred)`，凭据在调用前算好。
- 17.0：`persona_proc_adopt(p, persona, ^bool (kauth_cred_t parent, kauth_cred_t model) {...})`，
  凭据模型由块里的 `kauth_cred_model_setpersona()` 填。没有 persona 时 17 直接 `return ESRCH`。

移植的兜底（Sileo 用 persona 99 以 root 跑 apt/dpkg，没有 persona 就整个 spawn 失败）必须留着。
**取舍**：`persona == NULL` 时走移植的兜底（把 uid/gid/groups 直接设到进程的凭据上，并按
`persona_proc_adopt()` 的规则补 `chgproccnt()`）；否则走 17 的块 API。两条路都在补丁里。

### 2. `bsd/kern/kern_exec.c` —— `xpcproxy` 的 identity version：保留行为，丢掉不存在的函数

移植要的是"xpcproxy 变成它 spawn 的服务时不要新 pidversion"（否则 RunningBoard 的审计令牌与
entitlement 检查一直失败）。17 里这段在 exec 的末尾被重排过，而且
**`set_security_token_task_internal()` 在 10002 里已经不存在了**（在 `xnu-10002.1.13` 的 `bsd/`、`osfmk/`
里 `git grep` 零命中；16.5 里它在 `bsd/kern/kern_prot.c`）。所以：

- 保留 `xpcproxy_idversion` 这个 TUNABLE 和对 `proc_setpidversion()` 的保护；
- 丢掉 `task_set_uniqueid(task)` / `set_security_token_task_internal(...)` 两行：17 已经在上面做过
  `task_set_uniqueid(proc_task(p))`，重复调用没有意义。

### 3. `bsd/kern/kern_memorystatus.c` —— jetsam 的基准：**本次唯一的功能性退让**

16.5 的移植把 jetsam 阈值从 `max_mem` 改成 `sane_size`：这台机器（以及 redwood）的系统镜像是 RAM disk，
内核窗口的一半多是不可用内存，按 `max_mem` 算会杀掉活着的 daemon。17.0 把这段重写成
`MEMSTAT_PERCENT_TOTAL_PAGES(...)` 的编译期百分比 + 另一套 boot-arg 覆盖，结构完全不同。

4 处冲突**取 17 的版本**（保留 17 的代码结构），并把"要改回 sane_size 基准"写成文件里的
`ios17 TODO(port)` 注释。这是补丁层唯一的已知功能缺失，也是上机前的第一优先项：

```
ios17 TODO(port): 16.5's port sized these thresholds on sane_size, not on max_mem ...
```

### 4. `osfmk/arm/arm_init.c` —— 17 的函数签名多了一个参数

17 里 `configure_misc_apple_regs(bool is_boot_cpu)`（`osfmk/arm/machine_routines_apple.c`），
启动核传 `true`，从核传 `false`。取 17 的调用并补上 `true`，同时保留移植加的
`loader_checkpoint(33)`。

### 5. `osfmk/conf/files.arm64` —— amcc/PPL 的文件在 17 里只剩头文件

16.5 里移植往 `files.arm64` 加了 4 个 `amcc_rorgn_*` 的 `optional nos_arm_asm` 条目；17.0 的树里
`osfmk/arm64/` 只有 `amcc_rorgn.h`，`.c` 已经不在那个位置（Apple 重排了 PPL 的代码）。
**取舍**：取 17 的 `files.arm64`（这四行被 Apple 注释掉），移植的那几个 `.c` 还在 `xnu/files/` 里、
但因为不在 `files.arm64` 里而不参与编译。这块（指针认证 / PPL 的 amcc 寄存器固化）要按 17 的新位置重做。

### 6. `osfmk/kern/percpu.h` —— 取 17 的（移植的 UB 修复 17 已经做了）

16.5 的移植把 `percpu_foreach_secondary` 里的指针运算换成 `__unsafe_forge_bidi_indexable()` 的整数运算，
因为 `start = VM_MAX_KERNEL_ADDRESS, end = 0` 时 `start <= start + n` 会被 clang 18 判成真，循环多跑一次、
panic 在 `mbuf_mtypes_sync()`。17.0 把它改成整型比较（`(vm_address_t)__base_ <= (vm_address_t)__end_`），
**同一个修复**。取 17 的，移植的那段注释保留在上面说明为什么这里必须小心。

## 三、23 个直接 apply 会失败的 Apple 文件（记录用）

`bsd/kern/decmpfs.c`、`kern_exec.c`、`kern_memorystatus.c`、`kpi_socket.c`、`sys_generic.c`、
`uipc_syscalls.c`；`bsd/nfs/nfs_serv.c`；`bsd/sys/uio_internal.h`；`bsd/vfs/vfs_attrlist.c`、
`vfs_conf.c`、`vfs_lookup.c`、`vfs_quota.c`、`vfs_subr.c`、`vfs_syscalls.c`、`vfs_vnops.c`；
`config/MASTER.arm64.bcm2837`；`iokit/KernelConfigTables.cpp`；`osfmk/arm/arm_init.c`；
`osfmk/arm64/machine_routines.c`；`osfmk/conf/files.arm64`；`osfmk/kern/percpu.h`；
`osfmk/kern/sched_clutch.c`；`security/mac_vfs_subr.c`（完整日志见 `rebase/apply-reject.log`）。

`config/MASTER.arm64.bcm2837` 和 `iokit/KernelConfigTables.cpp` 在变基里没有冲突，因为它们是移植自己
新增/改写的配置表，17 那边没有对应改动。

## 四、变基带出来的"17 与 16.5 不同"清单（写驱动时要用）

| 16.5 里有 | 17.0 里 | 影响 |
|---|---|---|
| `set_security_token_task_internal()` | **删掉了** | 任何直接调它的移植代码都要改走 `kauth_cred_proc_update()` / `task_set_uniqueid()` |
| `persona_proc_adopt(p, persona, cred)` | 换成凭据模型的块 | persona 相关代码全要改（`kern_exec.c` 已处理） |
| `UIO_STACKBUF`（移植自加） | `uio_stackbuf_t` typedef | 37 处调用点已改 |
| `configure_misc_apple_regs()` | `configure_misc_apple_regs(bool)` | `arm_init.c` 已改 |
| jetsam 按 `max_mem` 百分比 / 移植改 `sane_size` | 编译期 `MEMSTAT_PERCENT_TOTAL_PAGES` | 见第二节第 3 条，**未完成** |
| `osfmk/arm64/amcc_rorgn_*.c` | 只剩 `amcc_rorgn.h` | PPL/amcc 要重做 |

## 五、还没做的（按优先级）

1. **编一遍**。需要 Linux + clang/lld + theos（`xnu-deps/setup.sh`），SDK overlay 与两个外部库要按 10002
   重做（`--rebuild-libs`）；50 个驱动对 17 的编译没有人验证过。变基只保证"打得上"，不保证"编得过"。
2. **jetsam 的 `sane_size` 基准**（第二节第 3 条）。
3. **amcc / PPL**（第二节第 5 条）。
4. **HFS Plus**：`apply.sh` 需要 `HAKIOS=/path/to/hakios` 才会把 `xnu/hfs/hfs.sh put` 跑起来。
5. **用户态**：iOS 17.0 不再支持 A11，IPSW 与 `sysimage/unpack.sh` 的成员名、大小、dyld cache 目录、
   `select-system.py` 清单都要按 21A329 改（`version.env` 已钉版本与机型）。
6. **Metal**：`hakios-metal` 只认 Adreno 642L；17.0 的 CoreAnimation 库版本也变了，
   `tools/ca-metallib.py` 的输入要跟着换。
