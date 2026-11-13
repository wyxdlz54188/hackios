#!/usr/bin/env python3
"""The SoC boot-arguments of a Qualcomm phone, from its device tree -- for SM8250 ("kona").

usage: tools/soc-args-kona.py DEVICE-TREE.dtb

Same output and same rules as the common repository's tools/soc-args.py, with the three lookups this
phone's vendor tree needs (they are the reference phone's node names, not kona's):

  soc_cmd_db        the common tool looks for a node named cmd_db; on kona the reservation is
                    /reserved-memory/reserved-memory@80860000 with compatible "qcom,cmd-db".
  modem_ipa_fw_at   the common tool looks for a node named ipa_gsi; on kona it is
                    /reserved-memory/pil_ipa_gsi_region@8e210000.
  soc_mpss_mem      the modem's own region: this tree has NO node for it (OnePlus' vendor tree keeps
                    the modem's carveout out of the FDT the kernel sees), so it stays missing and is
                    reported as such. It is the one value a first boot needs that this tree cannot give.

Register tuples use their immediate parent's #address-cells and #size-cells. Addresses wider than a
kernel argument can hold are refused rather than truncated. No bus-address translation is performed.
Only numbers are read out; no part of the tree is copied.
"""
import struct
import sys


def nodes_of(blob):
    if blob[:4] != b'\xd0\x0d\xfe\xed':
        sys.exit('soc-args-kona.py: not a flattened device tree')
    off_struct, off_strings = struct.unpack('>II', blob[8:16])
    size_strings, = struct.unpack('>I', blob[32:36])
    strings = blob[off_strings:off_strings + size_strings]
    out, path, at = {}, [], off_struct
    while True:
        token, = struct.unpack('>I', blob[at:at + 4])
        at += 4
        if token == 1:                                  # FDT_BEGIN_NODE
            end = blob.index(b'\0', at)
            path.append(blob[at:end].decode())
            at = (end + 4) & ~3
            out['/'.join(path)] = {}
        elif token == 2:                                # FDT_END_NODE
            path.pop()
        elif token == 3:                                # FDT_PROP
            length, name_off = struct.unpack('>II', blob[at:at + 8])
            at += 8
            name = strings[name_off:strings.index(b'\0', name_off)].decode()
            out['/'.join(path)][name] = blob[at:at + length]
            at = (at + length + 3) & ~3
        elif token == 9:                                # FDT_END
            return out
        elif token != 4:                                # 4 = FDT_NOP
            sys.exit(f'soc-args-kona.py: unexpected token {token}')


def find(nodes, compatible):
    for path, props in nodes.items():
        if compatible.encode() in props.get('compatible', b'').split(b'\0'):
            return path, props
    return None, None


def find_named(nodes, leaf):
    """The node whose last path component begins with `leaf` (apps-smmu@...; several share a compatible)."""
    for path, props in nodes.items():
        if path.rsplit('/', 1)[-1].split('@', 1)[0] == leaf:
            return path, props
    return None, None


def find_prefix(nodes, prefix):
    """First node whose last path component begins with `prefix` (pil_ipa_gsi_region@8e210000)."""
    for path, props in nodes.items():
        if path.rsplit('/', 1)[-1].startswith(prefix):
            return path, props
    return None, None


def u32(value, index=0):
    return struct.unpack_from('>I', value, index * 4)[0]


def reg_address(nodes, path, index=0):
    if path is None or 'reg' not in nodes[path]:
        return None
    parent = nodes[path.rsplit('/', 1)[0]]

    def width(name, default, allowed):
        value = parent.get(name, struct.pack('>I', default))
        if len(value) != 4 or u32(value) not in allowed:
            sys.exit(f'soc-args-kona.py: {path}: unsupported or malformed {name}')
        return u32(value)

    address_cells = width('#address-cells', 2, (1, 2))
    size_cells = width('#size-cells', 1, (0, 1, 2))
    stride = 4 * (address_cells + size_cells)
    data = nodes[path]['reg']
    if len(data) % stride:
        sys.exit(f'soc-args-kona.py: {path}: reg does not contain complete address/size tuples')
    at = index * stride
    if at >= len(data):
        return None
    return int.from_bytes(data[at:at + 4 * address_cells], 'big')


def aoss_mailbox(nodes):
    """AOSS QMP: mainline calls it *-aoss-qmp, a vendor tree qcom,qmp-aop@c300000 with qcom,qmp-mbox."""
    for path, props in nodes.items():
        kinds = props.get('compatible', b'').split(b'\0')
        if any(k.startswith(b'qcom,') and k.endswith(b'-aoss-qmp') for k in kinds):
            address = reg_address(nodes, path)
            if address is not None:
                return address
    for path, props in nodes.items():
        if path.rsplit('/', 1)[-1].split('@', 1)[0] == 'qcom,qmp-aop':
            address = reg_address(nodes, path)
            if address is not None:
                return address
    return None


def main():
    sys.stdout.reconfigure(newline="\n")        # LF on Windows too: the output becomes a file of boot-args
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    nodes = nodes_of(open(sys.argv[1], 'rb').read())
    args = []

    def address(arg, value, bits=32):
        if value is not None:
            if not 0 <= value < 1 << bits:
                sys.exit(f'soc-args-kona.py: {arg}={value:#x} does not fit the kernel\'s {bits}-bit argument')
            args.append((arg, value))

    path, _ = find(nodes, 'qcom,ipa')
    ipa_region, gsi_base = reg_address(nodes, path), reg_address(nodes, path, 1)
    if ipa_region is not None and gsi_base is not None:
        address('soc_ipa_base', ipa_region + 0x40000, bits=64)  # the IPA registers are 0x40000 into the region
        address('soc_gsi_base', gsi_base, bits=64)

    def block(compatible, arg, index=0):
        path, _ = find(nodes, compatible)
        address(arg, reg_address(nodes, path, index))

    block('qcom,ipcc', 'soc_ipcc')
    aoss = aoss_mailbox(nodes)
    if aoss is not None:
        address('soc_aoss', aoss)
    block('qcom,rpmh-rsc', 'soc_rsc', index=2)
    path, _ = find_named(nodes, 'apps-smmu')
    address('soc_apps_smmu', reg_address(nodes, path))

    by_phandle = {}
    for path, props in nodes.items():
        if 'phandle' in props:
            by_phandle[u32(props['phandle'])] = (path, props)

    def reserved(leaf, arg, prefix=False):
        path, _ = find_prefix(nodes, leaf) if prefix else find_named(nodes, leaf)
        address(arg, reg_address(nodes, path))

    # kona: the reservation carries the compatible qcom,cmd-db, not the node name cmd_db
    path, _ = find(nodes, 'qcom,cmd-db')
    address('soc_cmd_db', reg_address(nodes, path))
    reserved('pil_modem', 'soc_mpss_mem', prefix=True)
    reserved('modem_region', 'soc_mpss_mem', prefix=True)
    reserved('mpss', 'soc_mpss_mem', prefix=True)
    # kona: pil_ipa_gsi_region@8e210000 is where the IPA's firmware is loaded
    reserved('pil_ipa_gsi', 'modem_ipa_fw_at', prefix=True)
    reserved('ipa_gsi', 'modem_ipa_fw_at', prefix=True)
    _, smem = find(nodes, 'qcom,smem')
    if smem and 'memory-region' in smem:
        target = by_phandle.get(u32(smem['memory-region']))
        if target:
            address('soc_smem', reg_address(nodes, target[0]))
    path, _ = find(nodes, 'qcom,msm-imem')
    imem = reg_address(nodes, path)
    if imem is not None:
        address('soc_imem', imem & ~0x1fffff)         # the 2 MB block that holds it

    def stream(compatible, arg):
        _, props = find(nodes, compatible)
        if props and 'iommus' in props and len(props['iommus']) >= 8:
            args.append((arg, u32(props['iommus'], 1)))

    stream('qcom,ipa-smmu-ap-cb', 'soc_ipa_stream')
    stream('qcom,ipa-smmu-uc-cb', 'soc_ipa_stream_uc')

    def pas_id(leaf, arg, prefix=False):
        _, props = find_prefix(nodes, leaf) if prefix else find_named(nodes, leaf)
        if props and 'qcom,pas-id' in props:
            args.append((arg, u32(props['qcom,pas-id'])))

    pas_id('qcom,mss', 'soc_pas_mpss')
    pas_id('mss', 'soc_pas_mpss', prefix=True)
    pas_id('qcom,ipa_fws', 'soc_pas_ipa')
    pas_id('ipa_fws', 'soc_pas_ipa', prefix=True)

    _, ipa_fws = find_named(nodes, 'qcom,ipa_fws')
    ipa_fw_name = None
    if ipa_fws and 'qcom,firmware-name' in ipa_fws:
        ipa_fw_name = ipa_fws['qcom,firmware-name'].split(b'\0')[0].decode()

    for name, value in args:
        print(f'{name}={value:#x}')
    if ipa_fw_name:
        print(f'soc_ipa_fw={ipa_fw_name}')
    if not args:
        sys.exit('soc-args-kona.py: found none of the expected nodes; is this the phone\'s own device tree?')

    # what the tree cannot give, said out loud rather than left as a silent gap
    missing = [n for n in ('soc_mpss_mem', 'soc_pas_mpss', 'soc_cmd_db', 'modem_ipa_fw_at') if n not in
               dict(args)]
    if missing:
        print('soc-args-kona.py: not in this tree: ' + ', '.join(missing) +
              ' (docs/device-report.md says why and what fills it)', file=sys.stderr)


if __name__ == '__main__':
    main()
