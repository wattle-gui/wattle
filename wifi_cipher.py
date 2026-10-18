# wifi_cipher.py -- ON THE BOARD. Seals the Wi-Fi name and password so wifi.dat holds scrambled text, not plain words.
#
# seal(text)   -> one line "wattle1:<base64>"     (used by wifi_setup.py on the computer, which runs it on the board)
# unseal(line) -> the text again, or None         (used by Runtime.wifi())
#
# How: AES-256 in CBC mode (the board's own cryptolib). The key is made from the CHIP'S UNIQUE ID (machine.unique_id) plus a
# fixed label, so a wifi.dat copied to another board cannot be read there. Every sealing uses a new random start value, and the
# plain text begins with a marker so a wrong key (or a damaged file) is noticed instead of giving garbage.
#
# WHAT THIS DOES AND DOES NOT PROTECT: it stops casual reading, for example when wifi.dat shows up in a backup, a screenshot or a
# file listing, and it makes a stray copy useless on other boards. It is NOT strong protection against someone who has the board
# in their hands and knows this program: the key comes from the chip itself and this code is public. Real protection needs the ESP32's
# flash encryption, which is complicated and cannot be undone. Keep the board, and any copy of wifi.dat, to yourself.
import binascii
import hashlib
import os

import cryptolib
import machine

TAG = "wattle1:"
_MARK = b"WT1\n"


def _key():
    return hashlib.sha256(b"wattle-wifi-1" + machine.unique_id()).digest()      # 32 bytes = AES-256


def seal(text):
    data = _MARK + text.encode()
    pad = 16 - len(data) % 16                                                     # PKCS#7 padding to whole 16-byte blocks
    data += bytes([pad]) * pad
    iv = os.urandom(16)
    return TAG + binascii.b2a_base64(iv + cryptolib.aes(_key(), 2, iv).encrypt(data)).decode().strip()


def unseal(line):
    try:
        raw = binascii.a2b_base64(line.strip()[len(TAG):])
        iv, body = raw[:16], raw[16:]
        if len(iv) != 16 or not body or len(body) % 16:
            return None
        data = cryptolib.aes(_key(), 2, iv).decrypt(body)
        data = data[:-data[-1]]
        if data[:len(_MARK)] != _MARK:
            return None
        return data[len(_MARK):].decode()
    except Exception:
        return None
