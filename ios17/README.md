# ios17/ —— 这个移植的 iOS 17.0.0 目标

上游 HakiOS 的内核补丁是写给 iOS 16.5 的 XNU（`xnu-8796.121.2`）。这个目录是同一份工作
**变基到 iOS 17.0 的 XNU（`xnu-10002.1.13`，Darwin 23.0.0）** 的结果，以及把它复现出来的脚本。

| 文件 | 是什么 |
|---|---|
| `version.env` | 版本钉死：XNU tag/commit、Darwin、iOS build、目标机型 |
| `hakios-xnu-10002.1.13.patch` | **产物**：16.5 的移植 + 17.0 的 XNU（203 个文件，3.7 MB） |
| `apply.sh` | 拉 `xnu-10002.1.13` 并把补丁打上去，建 `xnu-src/xnu-10002.1.13/`（分支 `hakios17`） |
| `REBASE.md` | **变基报告**：46 处冲突逐个说明取舍，17 与 16.5 的差异清单，还没做的事 |
| `rebase/apply-reject.log` | 不走变基、直接 `git apply --reject` 到 10002 时留下的 23 个 `.rej` 的日志 |
| `rebase/analysis.json` | 机器可读的分析：被触碰文件的 churn、失败列表 |

## 做法

```sh
# 在公共仓库（hakios-xnu-kernel）的根目录，把本仓库放成 devices/oneplus8t/
make oneplus8t_defconfig
HAKIOS=$PWD devices/oneplus8t/ios17/apply.sh
# -> xnu-src/xnu-10002.1.13/，分支 hakios17，工作区未提交（xnu/export.sh 的输入形态）

./xnu-build.sh -j8 -k        # 尚未在此树上验证
```

`apply.sh` 依赖公共仓库的两个东西，缺了会明说：`tools/hakios-config.py` 生成的
`config/MASTER.hakios`、`bsd/dev/hakios.drivers.h`，以及 `xnu/hfs/hfs.sh` 的 HFS Plus。

## 验证（不需要编译就能跑的）

```sh
tools/check-ios17-tree.py            # 默认看 xnu-src/xnu-10002.1.13
```

它扫整棵树，看还有没有调用 17.0 删掉/改签名的那几个 API：`UIO_STACKBUF`、
`set_security_token_task_internal`、`persona_proc_adopt(..., cred)`、`configure_misc_apple_regs()`，
以及那一条 `ios17 TODO(port)` 是否还在原处。在 `ios17/apply.sh` 建出来的树上跑是干净的
（3758 个源文件，5 项都符合）。改驱动之后也该再跑一次。

## 状态

- 补丁：**在干净的 `xnu-10002.1.13` 上 `git apply --check` 通过**；变基过程与每一处取舍有记录。
- 编译：**没做过**。需要 Linux + clang/lld + theos；变基只保证语义合并，不保证 17 的 API 全对。
- 上机：**没有**。设备侧（UEFI、驱动）见 `docs/port-checklist.md`。
- 已知功能缺失：jetsam 的 `sane_size` 基准（见 `REBASE.md` 第二节第 3 条），代码里有 `ios17 TODO(port)`。
