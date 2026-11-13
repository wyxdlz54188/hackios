# kona 的 SoC 事实：EPSS、TSENS、SOCINFO

第 3 步 order 1 的三个驱动（`CPUFREQ`、`THERMAL`、`SOCINFO`）要的是"SoC 的地址"，不是"板子的地址"。
这里把本机设备树里的三组数字抄下来，并说明上游驱动哪一部分能直接用、哪一部分必须换。

## 1. CPU 频率（EPSS）

本机设备树 `/soc/qcom,cpufreq-hw`（compatible `qcom,cpufreq-hw-epss`）：

```
reg = <0x18591000 0x1000>, <0x18592000 0x1000>, <0x18593000 0x1000>
interrupts = dcvsh0_int, dcvsh1_int, dcvsh2_int
qcom,lut-row-size = 4
#freq-domain-cells = 2
```

三组 0x1000，间隔 0x1000，**和上游驱动里的 `EPSS_PHYS 0x18591000`、`EPSS_DOMAIN_SIZE 0x1000`、
`EPSS_DOMAINS 3` 完全一致** —— 这组地址是 SoC 的固定 IP 偏移，不是板子的。核的归属也一致：

| 域 | 核 | 集群 |
|---|---|---|
| 0 | cpu0–cpu3 | 4× Cortex-A55（能效） |
| 1 | cpu4–cpu6 | 3× Cortex-A77（大核） |
| 2 | cpu7 | 1× Cortex-A77（超大核） |

所以 `CONFIG_HAKIOS_CPUFREQ=y` + `cpufreq=1` 在本机**很可能不用改地址**；要验证的是"每域的频率表行数"
（`qcom,lut-row-size=4`，驱动取最高一行）和切换后频率是否真的变（`sysctl kern.hakios.cpu*`）。
这是 order 1 里最省事的一个。

## 2. 温度传感器（TSENS）

本机有两个块，都是 `qcom,tsens24xx`（上游驱动/工具认的是 `qcom,tsens26xx`，**寄存器布局同为
tsens-v2**，这也是 Linux 的 `tsens-v2.c` 同时管这两个 compatible 的原因）：

| 块 | SRoT 基址 | 温度状态字基址（TM） | 属性 |
|---|---|---|---|
| TM0 | `0xc222000` | **`0xc263000`**（0x1ff 字节） | 16 个传感器（cpu-0-*, cpuss-*, cpu-1-*, aoss0, gpuss-0） |
| TM1 | `0xc223000` | **`0xc265000`**（0x1ff 字节） | 9 个传感器（aoss-1, cwlan, video, ddr, q6-hvx, camera, cmpss, npu, gpuss-1） |

两个 TM 基址与上游驱动里的 `REFERENCE_TM0 0xc263000` / `REFERENCE_TM1 0xc265000` **相同**，
状态字布局 `0xa0 + 4*n`、valid bit 21 也相同 —— **读的代码不用改，只有传感器表要换**。

表已经从本机设备树生成：`soc/thermal/kona-thermal-table.h`（25 个传感器，含厂商自己的
降频/放弃温度）。本机设备树一共 **99 个 thermal zone**，其中 25 个挂在 TSENS 上；其余是 PMIC
（`pm8150*_tz`、bcl/ibat/vbat/vph）、modem 自己的和虚拟的 `soc`/`skin-*`/`pop-mem`，这个驱动按设计
不读它们。

用法：把驱动里的 `sensors[]` 换成这张表（或按上游的"设备自带驱动"机制，把 `hakios.thermal.c` 复制到
`drivers/power/` 下改表）。**注意** `cpu-1-*` 的厂商降频点是 75 °C（不是 108），这是 OnePlus 自己的
保守设定，照抄即可。

## 3. 芯片身份（SOCINFO）

上游驱动读的是 SMEM 里的 `socinfo` 结构（item 137），SMEM 区域 `0x200000` 字节、地址来自
`soc_smem`。本机：

- `soc.args` 的 `soc_smem=0x80900000`（来自本机设备树 `/soc/qcom,smem` → `/reserved-memory/smem_region@80900000`）
- 尺寸：本机 DT 就是 `0x200000`，与驱动假设一致

所以 `CONFIG_HAKIOS_SOCINFO=y` + `socinfo=1` 不需要改代码；跑起来后 `kern.hakios.soc_*` 应当报
SM8250（soc_id 356，与 `ro.boot.platform_id=356` 对得上）。

## 结论

| 驱动 | 地址/布局 | 要改的 |
|---|---|---|
| `CPUFREQ` | 与驱动一致（0x18591000，3 个域） | 无（验证频率表与切换） |
| `THERMAL` | TM 基址一致（0xc263000/0xc265000） | **只换 `sensors[]` 表**（`soc/thermal/kona-thermal-table.h`） |
| `SOCINFO` | 走 `soc_smem`，本机 0x80900000/2 MB | 无 |

三个都可以在"空驱动首启"之后立刻打开，作为 order 1 的第一批。
