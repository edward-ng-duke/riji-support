#!/usr/bin/env python3
"""Decode the complete public RJPL v1 database into a GeoJSON FeatureCollection."""
import argparse
import json
import struct
from pathlib import Path


def decode(source):
    data = source.read_bytes()
    offset = 0

    def read(fmt):
        nonlocal offset
        values = struct.unpack_from('<' + fmt, data, offset)
        offset += struct.calcsize('<' + fmt)
        return values[0] if len(values) == 1 else values

    if data[:4] != b'RJPL':
        raise ValueError('Expected RJPL database')
    offset = 4
    if read('H') != 1:
        raise ValueError('Unsupported RJPL version')
    strings = []
    for _ in range(read('I')):
        length = read('H')
        strings.append(data[offset:offset + length].decode('utf-8'))
        offset += length
    features = []
    for _ in range(read('I')):
        district, city, province = read('HHB')
        bounds = list(read('4f'))
        polygons = []
        for _ in range(read('H')):
            hole = read('B')
            points = [list(read('ff')) for _ in range(read('I'))]
            if hole:
                if not polygons:
                    raise ValueError('Hole without exterior ring')
                polygons[-1].append(points)
            else:
                polygons.append([points])
        features.append({
            'type': 'Feature',
            'properties': {
                'district': strings[district],
                'city': None if city == 0xFFFF else strings[city],
                'province_fallback': bool(province),
            },
            'bbox': bounds,
            'geometry': {'type': 'MultiPolygon', 'coordinates': polygons},
        })
    if offset != len(data):
        raise ValueError('Unexpected trailing bytes')
    return {'type': 'FeatureCollection', 'features': features}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', nargs='?', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'places-cn.bin')
    parser.add_argument('target', type=Path)
    args = parser.parse_args()
    document = decode(args.source)
    args.target.write_text(json.dumps(document, ensure_ascii=False) + '\n')
    print(f"Decoded {len(document['features'])} regions to {args.target.name}")


if __name__ == '__main__':
    main()
