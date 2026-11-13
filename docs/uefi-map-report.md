# UEFI 内存映射 vs 本机设备树：这次运行的完整输出

工具：`tools/check-uefi-map.py`（本仓库），输入是 Mu-Silicium 的
`Platforms/OnePlus/kebabPkg/Library/MemoryMapLib/MemoryMapLib.c` 和本机的
`prebuilt/device-tree.dtb`（`/sys/firmware/fdt`，787 882 字节）。日期 2026-11-13。

```text
UEFI map: 42 regions; this phone's tree: 23 reservations

== fixed UEFI windows that sit on one of this phone's reservations ==
  UEFI Display Reserved 0x009c000000 +  36.0 MB  on  cont_splash_region@9c000000        0x009c000000 +  35.0 MB
  UEFI Display Reserved 0x009c000000 +  36.0 MB  on  disp_rdump_region@9c000000         0x009c000000 +   8.0 MB
  UEFI Display Reserved 0x009c000000 +  36.0 MB  on  dfps_data_region@9e300000          0x009e300000 +   1.0 MB
  UEFI UEFI FD        0x009fc00000 +   3.0 MB  on  kboot_uboot_logmem@0x9FE00000      0x009fe00000 +   2.0 MB
  UEFI SEC Heap       0x009ff00000 +   0.5 MB  on  kboot_uboot_logmem@0x9FE00000      0x009fe00000 +   2.0 MB
  UEFI MMU PageTables 0x009ff8d000 +   0.0 MB  on  kboot_uboot_logmem@0x9FE00000      0x009fe00000 +   2.0 MB
  UEFI UEFI Stack     0x009ff90000 +   0.2 MB  on  kboot_uboot_logmem@0x9FE00000      0x009fe00000 +   2.0 MB
  UEFI Log Buffer     0x009fff7000 +   0.0 MB  on  kboot_uboot_logmem@0x9FE00000      0x009fe00000 +   2.0 MB
  UEFI Info Blk       0x009ffff000 +   0.0 MB  on  kboot_uboot_logmem@0x9FE00000      0x009fe00000 +   2.0 MB
  UEFI DXE Heap       0x00b0000000 +  69.0 MB  on  ramoops@0xB0000000                 0x00b0000000 +   4.0 MB

== this phone's reservations the UEFI map does not cover ==
  0x0080700000 +     1.4 MB  xbl_aop_region@80700000
  0x0094000000 +     1.0 MB  pil_spss_region@94000000
  0x0094100000 +    70.0 MB  cdsp_secure_heap@94100000

3 of 23 reservations are not in the UEFI map. Expected for Android-only carveouts (splash, dfps, ramoops),
worth checking for anything a firmware block owns (PIL, ADSP, modem).
```

## 怎么读这份输出

**`Display Reserved` 压住 splash / rdump / dfps —— 正常**：kebab 的 UEFI 把整段 0x9C000000 起
36 MB 当作显示保留区，本机 Android 在这段里放开机图（35 MB）、rdump（8 MB）和 DFPS 数据（1 MB），
三者都在 36 MB 之内。这正是"同一段内存，两个系统各自命名"的情况，不是冲突。

**`FD` 与它上面的几个窗口压住 `kboot_uboot_logmem` —— 需要知道，但先不改**：
OnePlus 的 ABL/U-Boot 在 0x9FE00000 留了 2 MB 存自己的日志；HakiOS 的启动链里没有 OnePlus 的 U-Boot，
这段在 UEFI 跑的时候没有写者。kebab 平台也是这么放的，说明 Project Silicium 认为可以。

**`DXE Heap` 压住 `ramoops` —— 同上**：0xB0000000 起 4 MB 是 Android 的 pstore（上一次内核崩溃的日志）。
UEFI 的 DXE 堆从同一地址起 69 MB，跑起来会把它写掉。HakiOS 从 RAM 启动、不读 ramoops，所以接受；
**如果**首启在写日志时崩，第一个要试的改法就是把 `DXE Heap` 挪到 `0xB0400000`、大小改成 `0x4100000`。

**三段没被覆盖的保留区 —— 只有一段值得盯**：
`xbl_aop_region`（0x80700000，1.4 MB）是 XBL/AOP 的日志区，UEFI 不碰它没有关系（AOP 已启动）。
`pil_spss_region`（1 MB）和 `cdsp_secure_heap`（70 MB）在 0x94000000 起：kebab 的 `PIL Reserved`
到 0x92400000 就结束，中间空出 0x92400000–0x9BC00000 约 150 MB。如果 UEFI 的 DXE 把这段当空闲内存
分配出去，而之后又有谁去加载 SPSS/CDSP，就会撞车。这个移植的 XNU 不加载它们，所以列为观察项。
