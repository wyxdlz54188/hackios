/*
 * The OnePlus 8T's (SM8250 "kona") temperature sensors, as drivers/power/hakios.thermal.c wants them:
 * name, the TSENS block the reading is in (the address of its status words), the sensor's number in
 * that block, the temperature the vendor starts to slow things down at, and the one it gives up at,
 * in millidegrees.
 *
 * Made by tools/dt-thermal.py from this phone's own device tree (prebuilt/device-tree.dtb):
 *     python3 tools/dt-thermal.py prebuilt/device-tree.dtb --c
 * The numbers are the vendor's trip points, out of /soc/thermal-zones/*-step and *-usr; nothing here is
 * invented. Do not edit by hand: make it again.
 *
 * Against the reference phone's table (redwood, SC7280, in the common driver): the two TSENS blocks sit
 * at the same addresses (0xc263000 and 0xc265000, tsens-v2 status words at 0xa0 + 4 * n -- the driver's
 * read path needs no change), but the sensors are not the same set: 25 here against 27 there, with the
 * GPU's two (gpuss-0 on TM0 sensor 15, gpuss-1 on TM1 sensor 8) where that phone has nspss/mdmss.
 *
 * To use it, the common driver's `sensors[]` table is replaced by this one -- the rest of
 * drivers/power/hakios.thermal.c (TM_SIZE, TM_STATUS, the polling, the stop) stays as it is. RECOMMENDED
 * PATH: a device that carries a driver of its own (devices/<name>/drivers/<subsystem>/conf, docs/porting/
 * drivers.md), so the common tree keeps its reference phone's table. Not done yet: this file is the
 * table, and the driver change (or the device's copy of the driver) is the next step.
 */
	{ "aoss0",   0xc263000,  0, 115000, 125000 },
	{ "cpu-0-0", 0xc263000,  1, 110000, 125000 },
	{ "cpu-0-1", 0xc263000,  2, 110000, 125000 },
	{ "cpu-0-2", 0xc263000,  3, 110000, 125000 },
	{ "cpu-0-3", 0xc263000,  4, 110000, 125000 },
	{ "cpuss-0", 0xc263000,  5, 115000, 125000 },
	{ "cpuss-1", 0xc263000,  6, 115000, 125000 },
	{ "cpu-1-0", 0xc263000,  7,  75000, 125000 },
	{ "cpu-1-1", 0xc263000,  8,  75000, 125000 },
	{ "cpu-1-2", 0xc263000,  9,  75000, 125000 },
	{ "cpu-1-3", 0xc263000, 10,  75000, 125000 },
	{ "cpu-1-4", 0xc263000, 11,  75000, 125000 },
	{ "cpu-1-5", 0xc263000, 12,  75000, 125000 },
	{ "cpu-1-6", 0xc263000, 13,  75000, 125000 },
	{ "cpu-1-7", 0xc263000, 14,  75000, 125000 },
	{ "gpuss-0", 0xc263000, 15, 115000, 125000 },
	{ "aoss-1",  0xc265000,  0, 115000, 125000 },
	{ "cwlan",   0xc265000,  1, 100000, 125000 },
	{ "video",   0xc265000,  2, 100000, 125000 },
	{ "ddr",     0xc265000,  3,  95000, 125000 },
	{ "q6-hvx",  0xc265000,  4, 100000, 125000 },
	{ "camera",  0xc265000,  5, 100000, 125000 },
	{ "cmpss",   0xc265000,  6, 100000, 125000 },
	{ "npu",     0xc265000,  7, 100000, 125000 },
	{ "gpuss-1", 0xc265000,  8, 115000, 125000 },
