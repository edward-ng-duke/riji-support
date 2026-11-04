#!/usr/bin/env python3
"""从现有离线区县库派生 AI 可用行政地名白名单，不联网。

数据来源/许可同 build_places.py：geoBoundaries CHN ADM3（ODbL 1.0，OpenStreetMap）
和 GeoNames（CC BY 4.0）。更新 places-cn.bin 后运行本脚本，同步 AI 地名白名单。
只输出行政地名；不含边界、坐标、街道或用户数据。
"""
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'places-cn.bin'
TARGET = ROOT / 'administrative-places.json'


def build(source=SOURCE, target=TARGET):
    data = source.read_bytes()
    offset = 0

    def read(fmt):
        nonlocal offset
        value = struct.unpack_from('<' + fmt, data, offset)
        offset += struct.calcsize('<' + fmt)
        return value[0] if len(value) == 1 else value

    assert data[:4] == b'RJPL'
    offset = 4
    assert read('H') == 1
    strings = []
    for _ in range(read('I')):
        length = read('H')
        strings.append(data[offset:offset + length].decode('utf-8'))
        offset += length
    names, provinces = set(), set()
    for _ in range(read('I')):
        district_index, city_index, province = read('HHB')
        read('ffff')
        for _ in range(read('H')):
            read('B')
            point_count = read('I')
            offset += point_count * 8
        district = strings[district_index]
        city = None if city_index == 0xFFFF else strings[city_index]
        if province:
            provinces.add(district)
            continue
        # GeoNames 的少量匹配落在镇（如昭平镇/良庆镇），不能作为区县放行。
        administrative_endings = ('市', '区', '县', '旗', '自治州', '地区', '盟')
        valid_district = district.endswith(administrative_endings) and not district.endswith(('社区', '小区'))
        if valid_district:
            names.add(district)
        if city and city.endswith(('市', '自治州', '地区', '盟')):
            names.add(city)
            if valid_district:
                names.add(district if district.startswith(city) else city + district)
    assert offset == len(data)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(dict(names=sorted(names), provinces=sorted(provinces)), ensure_ascii=False, indent=2) + '\n')
    print(f'{len(names)} names, {len(provinces)} province prefixes; {target.stat().st_size} bytes')


if __name__ == '__main__':
    build()
