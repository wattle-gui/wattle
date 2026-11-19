"""A small QR code maker, so the Editor can show a code that a phone camera scans (the board's web address) without any extra software.

Only what is needed: byte mode, error correction level M, versions 1 to 6 (text up to 106 characters). make_qr(text) returns the
square of dark/light modules as a list of rows of booleans (True = dark), without the quiet border."""
from __future__ import annotations

# version: (data codewords per block, number of blocks, error codewords per block) for level M
_BLOCKS = {1: (16, 1, 10), 2: (28, 1, 16), 3: (44, 1, 26), 4: (32, 2, 18), 5: (43, 2, 24), 6: (27, 4, 16)}
_ALIGN = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34]}
_MAX_BYTES = {1: 14, 2: 26, 3: 42, 4: 62, 5: 84, 6: 106}

_EXP = [0] * 512
_LOG = [0] * 256
_x = 1
for _i in range(255):
    _EXP[_i] = _x
    _LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    _EXP[_i] = _EXP[_i - 255]


def _rs_remainder(data: list[int], n: int) -> list[int]:
    gen = [1]
    for i in range(n):                                   # generator polynomial: (x - a^0)(x - a^1) ... (x - a^(n-1))
        nxt = [0] * (len(gen) + 1)
        for j, c in enumerate(gen):
            nxt[j] ^= c
            if c:
                nxt[j + 1] ^= _EXP[_LOG[c] + i]
        gen = nxt
    rem = [0] * n
    for d in data:
        factor = d ^ rem[0]
        rem = rem[1:] + [0]
        if factor:
            for j in range(n):
                if gen[j + 1]:
                    rem[j] ^= _EXP[_LOG[gen[j + 1]] + _LOG[factor]]
    return rem


def _codewords(text: bytes, version: int) -> list[int]:
    per_block, blocks, ec = _BLOCKS[version]
    total_data = per_block * blocks
    bits = "0100" + format(len(text), "08b") + "".join(format(b, "08b") for b in text)
    bits += "0" * min(4, total_data * 8 - len(bits))
    bits += "0" * (-len(bits) % 8)
    data = [int(bits[i:i + 8], 2) for i in range(0, len(bits), 8)]
    pad = (0xEC, 0x11)
    while len(data) < total_data:
        data.append(pad[(len(data) - len(bits) // 8) % 2])
    chunks = [data[i * per_block:(i + 1) * per_block] for i in range(blocks)]
    ecs = [_rs_remainder(c, ec) for c in chunks]
    out = [chunks[b][i] for i in range(per_block) for b in range(blocks)]
    out += [ecs[b][i] for i in range(ec) for b in range(blocks)]
    return out


def _format_bits(mask: int) -> int:
    data = (0b00 << 3) | mask                            # error correction level M = 00
    rem = data
    for _ in range(10):
        rem = (rem << 1) ^ ((rem >> 9) * 0x537)
    return ((data << 10) | rem) ^ 0x5412


def _build(version: int, words: list[int], mask: int) -> list[list[bool]]:
    n = 17 + 4 * version
    m = [[False] * n for _ in range(n)]
    fn = [[False] * n for _ in range(n)]                 # function patterns (not data)

    def put(r: int, c: int, dark: bool) -> None:
        m[r][c] = dark
        fn[r][c] = True

    def finder(r0: int, c0: int) -> None:
        for dr in range(-1, 8):
            for dc in range(-1, 8):
                r, c = r0 + dr, c0 + dc
                if 0 <= r < n and 0 <= c < n:
                    inside = 0 <= dr <= 6 and 0 <= dc <= 6
                    put(r, c, inside and (dr in (0, 6) or dc in (0, 6) or (2 <= dr <= 4 and 2 <= dc <= 4)))
    finder(0, 0)
    finder(0, n - 7)
    finder(n - 7, 0)
    for i in range(8, n - 8):                            # timing patterns
        put(6, i, i % 2 == 0)
        put(i, 6, i % 2 == 0)
    pos = _ALIGN[version]
    for r in pos:
        for c in pos:
            if fn[r][c]:
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    put(r + dr, c + dc, max(abs(dr), abs(dc)) != 1)
    put(n - 8, 8, True)                                  # the always-dark module
    for i in range(9):                                   # reserve the format areas
        for r, c in ((8, i), (i, 8)):
            if not fn[r][c]:
                put(r, c, False)
    for i in range(8):
        put(8, n - 1 - i, False)
        put(n - 1 - i, 8, False)
    put(n - 8, 8, True)
    bits = []
    for w in words:
        bits += [(w >> (7 - i)) & 1 for i in range(8)]
    k = 0
    c = n - 1
    upward = True
    while c > 0:
        if c == 6:
            c -= 1
        rows = range(n - 1, -1, -1) if upward else range(n)
        for r in rows:
            for cc in (c, c - 1):
                if not fn[r][cc]:
                    dark = bool(bits[k]) if k < len(bits) else False
                    k += 1
                    if (r + cc) % 2 == 0 if mask == 0 else (
                       r % 2 == 0 if mask == 1 else (
                       cc % 3 == 0 if mask == 2 else (
                       (r + cc) % 3 == 0 if mask == 3 else (
                       (r // 2 + cc // 3) % 2 == 0 if mask == 4 else (
                       (r * cc) % 2 + (r * cc) % 3 == 0 if mask == 5 else (
                       ((r * cc) % 2 + (r * cc) % 3) % 2 == 0 if mask == 6 else
                       ((r + cc) % 2 + (r * cc) % 3) % 2 == 0)))))):
                        dark = not dark
                    m[r][cc] = dark
        upward = not upward
        c -= 2
    fmt = _format_bits(mask)
    for i in range(15):
        bit = bool((fmt >> i) & 1)
        # first copy: around the top-left finder
        if i < 6:
            m[i][8] = bit
        elif i < 8:
            m[i + 1][8] = bit
        elif i == 8:
            m[8][7] = bit
        else:
            m[8][14 - i] = bit
        # second copy: below the top-right and right of the bottom-left finder
        if i < 8:
            m[8][n - 1 - i] = bit
        else:
            m[n - 15 + i][8] = bit
    m[n - 8][8] = True
    return m


def _penalty(m: list[list[bool]]) -> int:
    n = len(m)
    score = 0
    for grid in (m, [list(col) for col in zip(*m)]):     # rows, then columns
        for row in grid:
            run = 1
            for i in range(1, n):
                if row[i] == row[i - 1]:
                    run += 1
                else:
                    if run >= 5:
                        score += run - 2
                    run = 1
            if run >= 5:
                score += run - 2
            line = "".join("1" if x else "0" for x in row)
            for pat in ("10111010000", "00001011101"):
                start = 0
                while (j := line.find(pat, start)) != -1:
                    score += 40
                    start = j + 1
    for r in range(n - 1):
        for c in range(n - 1):
            if m[r][c] == m[r][c + 1] == m[r + 1][c] == m[r + 1][c + 1]:
                score += 3
    dark = sum(sum(row) for row in m)
    score += 10 * (abs(dark * 100 // (n * n) - 50) // 5)
    return score


def make_qr(text: str) -> list[list[bool]]:
    data = text.encode("utf-8")
    version = next((v for v in range(1, 7) if len(data) <= _MAX_BYTES[v]), None)
    if version is None:
        raise ValueError("text too long for the small QR maker (106 characters at most)")
    words = _codewords(data, version)
    best = min((_build(version, words, mask) for mask in range(8)), key=_penalty)
    return best
