#!/usr/bin/env python3
"""离线地名库：粗坐标 → 「上海市黄浦区」（只在本机查，不联网）。

数据来源（下载到任意目录，作为参数传入；原始数据不进 git）：
  - geoBoundaries CHN ADM3（区 / 县级边界，ODbL 1.0，源自 OpenStreetMap）
      https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/CHN/ADM3/geoBoundaries-CHN-ADM3_simplified.geojson
  - geoBoundaries CHN ADM1（省级边界，兜底港澳台等没有区县边界的地方）
      https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/CHN/ADM1/geoBoundaries-CHN-ADM1_simplified.geojson
  - GeoNames CN.zip（中文名与上级市 / 省，CC BY 4.0）
      https://download.geonames.org/export/dump/CN.zip

    python3 -I scripts/build_places.py <下载目录>

输出本公开数据目录中的 places-cn.bin。格式和完整读取器见 decode_places.py。
"""
import json
import math
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "places-cn.bin"
TOLERANCE = 0.003  # 道格拉斯-普克简化容差（度，约 300 米）；坐标本来就取整到 0.01°
CJK = re.compile(r"^[㐀-鿿]+$")
SUFFIXES = ("自治县", "自治旗", "地区", "林区", "特区", "新区", "区", "县", "市", "旗", "州", "盟")

# 省级中文名（geoBoundaries ADM1 是英文名，34 个直接列出）
PROVINCES = {
    "Anhui": "安徽省", "Beijing": "北京市", "Chongqing": "重庆市", "Fujian": "福建省", "Gansu": "甘肃省",
    "Guangdong": "广东省", "Guangxi": "广西壮族自治区", "Guizhou": "贵州省", "Hainan": "海南省", "Hebei": "河北省",
    "Heilongjiang": "黑龙江省", "Henan": "河南省", "Hong Kong": "香港", "Hubei": "湖北省", "Hunan": "湖南省",
    "Inner Mongolia": "内蒙古自治区", "Jiangsu": "江苏省", "Jiangxi": "江西省", "Jilin": "吉林省", "Liaoning": "辽宁省",
    "Macao": "澳门", "Macau": "澳门", "Ningxia": "宁夏回族自治区", "Qinghai": "青海省", "Shaanxi": "陕西省",
    "Shandong": "山东省", "Shanghai": "上海市", "Shanxi": "山西省", "Sichuan": "四川省", "Taiwan": "台湾",
    "Tianjin": "天津市", "Tibet": "西藏自治区", "Xinjiang": "新疆维吾尔自治区", "Xizang": "西藏自治区",
    "Yunnan": "云南省", "Zhejiang": "浙江省",
}


def hanzi(alternates: str) -> str | None:
    """从 GeoNames alternatenames 里挑中文名：优先带行政区后缀的，取最长。"""
    names = [a for a in alternates.split(",") if CJK.match(a)]
    if not names:
        return None
    suffixed = [n for n in names if n.endswith(SUFFIXES)]
    return max(suffixed or names, key=len)


def core(name: str) -> str:
    """名字的拼音主干，用于英文边界名 ↔ GeoNames 名对齐：「Huangpu District」「Huangpu Qu」→「huangpu」。"""
    n = name.lower().replace("’", "'")
    n = re.sub(r"\b(autonomous|district|county|city|banner|special|forestry|new area|area|qu|xian|shi|zizhixian|zizhiqi|qi|tequ|linqu|xinqu)\b", " ", n)
    return re.sub(r"[^a-z]", "", n)


def same(a: str, b: str) -> bool:
    """拼音主干相同；连写的「Chengqu」和分写的「Cheng Qu」也算。"""
    ca, cb = core(a), core(b)
    strip = lambda c: re.sub(r"(qu|xian|shi|qi)$", "", c)
    return bool(ca) and (ca == cb or strip(ca) == cb or ca == strip(cb))


def load_geonames(path: Path):
    adm1, adm2, adm3 = {}, {}, []
    with path.open(encoding="utf-8") as f:
        for line in f:
            c = line.rstrip("\n").split("\t")
            code = c[7]
            if code not in ("ADM1", "ADM2", "ADM3"):
                continue
            h = hanzi(c[3])
            if code == "ADM1":
                adm1[c[10]] = h
            elif code == "ADM2":
                adm2[(c[10], c[11])] = h
            else:
                adm3.append({"name": c[2], "core": core(c[2]), "hz": h, "lat": float(c[4]), "lon": float(c[5]),
                             "a1": c[10], "a2": c[11]})
    return adm1, adm2, adm3


def rings_of(geom):
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    for p in polys:
        for i, ring in enumerate(p):
            yield i > 0, [(pt[0], pt[1]) for pt in ring]


def inside(x, y, rings) -> bool:
    c = False
    for _, ring in rings:
        j = len(ring) - 1
        for i in range(len(ring)):
            xi, yi = ring[i]
            xj, yj = ring[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                c = not c
            j = i
    return c


def simplify(pts, tol):
    """道格拉斯-普克（迭代版），保留首尾。"""
    if len(pts) < 5:
        return pts
    keep = [False] * len(pts)
    keep[0] = keep[-1] = True
    stack = [(0, len(pts) - 1)]
    while stack:
        a, b = stack.pop()
        ax, ay = pts[a]
        bx, by = pts[b]
        dx, dy = bx - ax, by - ay
        norm = math.hypot(dx, dy)
        best, idx = -1.0, -1
        for i in range(a + 1, b):
            px, py = pts[i]
            d = abs(dy * (px - ax) - dx * (py - ay)) / norm if norm else math.hypot(px - ax, py - ay)
            if d > best:
                best, idx = d, i
        if best > tol:
            keep[idx] = True
            stack += [(a, idx), (idx, b)]
    out = [p for p, k in zip(pts, keep) if k]
    return out if len(out) >= 4 else pts


def km(lat1, lon1, lat2, lon2):
    return math.hypot((lat1 - lat2) * 111, (lon1 - lon2) * 111 * math.cos(math.radians(lat1)))


def main() -> None:
    src = Path(sys.argv[1])
    adm1, adm2, adm3 = load_geonames(src / "CN.txt")
    regions, stats = [], {"name": 0, "cjk": 0, "inside": 0, "city_only": 0, "nearby": 0, "none": 0}
    provinces = []
    for f in json.load((src / "CHN_ADM1.geojson").open())["features"]:
        n = f["properties"]["shapeName"]
        key = next((k for k in PROVINCES if n.startswith(k)), None)
        if key:
            provinces.append((PROVINCES[key], list(rings_of(f["geometry"]))))

    for f in json.load((src / "CHN_ADM3.geojson").open())["features"]:
        rings = list(rings_of(f["geometry"]))
        xs = [x for _, r in rings for x, _ in r]
        ys = [y for _, r in rings for _, y in r]
        box = (min(xs), min(ys), max(xs), max(ys))
        name = f["properties"]["shapeName"]
        cands = [g for g in adm3 if box[0] - 0.3 <= g["lon"] <= box[2] + 0.3 and box[1] - 0.3 <= g["lat"] <= box[3] + 0.3 and g["hz"]]
        named = [g for g in cands if same(name, g["name"])]
        within = [g for g in cands if inside(g["lon"], g["lat"], rings)]
        cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
        district = None
        if named:
            pick = min(named, key=lambda g: km(g["lat"], g["lon"], cy, cx)); stats["name"] += 1
            district = pick["hz"]
        elif CJK.match(name.replace(" ", "")) and name.endswith(SUFFIXES):
            # 边界数据本身就是中文名（新设的区县）：名字用它，上级市取最近的 GeoNames 区县
            pick = min(cands or adm3, key=lambda g: km(g["lat"], g["lon"], cy, cx)); stats["cjk"] += 1
            district = name
        elif len(within) == 1:
            # 只按位置对上：位置可靠，名字可能是旧称（撤并 / 更名前）
            pick = within[0]; stats["inside"] += 1
            district = pick["hz"]
        elif within:
            # 多个旧区合并成的新区：区名不可靠，只标到市（取离中心最近的旧区所属的市）
            pick = min(within, key=lambda g: km(g["lat"], g["lon"], cy, cx)); stats["city_only"] += 1
        elif (prov := next((pn for pn, pr in provinces if inside(cx, cy, pr)), None)) and (near := [
                g for g in cands if (adm1.get(g["a1"]) or "")[:2] == prov[:2] and km(g["lat"], g["lon"], cy, cx) < 30]):
            # 区内没有 GeoNames 区县点（新设 / 合并的区）：同省、离中心最近的区县所属的市，只标到市
            pick = min(near, key=lambda g: km(g["lat"], g["lon"], cy, cx)); stats["nearby"] += 1
        else:
            stats["none"] += 1
            continue
        city = adm2.get((pick["a1"], pick["a2"])) or adm1.get(pick["a1"])
        if district is None and city is None:
            stats["none"] += 1
            continue
        if district and city:
            # 「拉萨城关区」「长治郊区」这类为消歧带了市名的：去掉，显示时再拼成「拉萨市城关区」
            stem = re.sub(r"(市|地区|自治州|州|盟)$", "", city)
            if len(stem) >= 2 and district.startswith(stem) and len(district) > len(stem) + 1 and not district.startswith(city):
                district = district[len(stem):]
        regions.append({"district": district or city, "city": city if district else None, "rings": rings})

    # 省级兜底（港澳台等）：放在最后，区县都没命中时才用
    for pn, pr in provinces:
        regions.append({"district": pn, "city": None, "rings": pr, "province": True})

    strings, index = [], {}
    def sid(s):
        if s is None:
            return 0xFFFF
        if s not in index:
            index[s] = len(strings); strings.append(s)
        return index[s]

    body, points = bytearray(), 0
    for r in regions:
        rings = [(hole, simplify(pts, TOLERANCE)) for hole, pts in r["rings"]]
        xs = [x for _, p in rings for x, _ in p]
        ys = [y for _, p in rings for _, y in p]
        body += struct.pack("<HHB4fH", sid(r["district"]), sid(r["city"]), 1 if r.get("province") else 0,
                            min(xs), min(ys), max(xs), max(ys), len(rings))
        for hole, pts in rings:
            body += struct.pack("<BI", 1 if hole else 0, len(pts))
            body += b"".join(struct.pack("<ff", x, y) for x, y in pts)
            points += len(pts)

    head = bytearray(b"RJPL") + struct.pack("<HI", 1, len(strings))
    for s in strings:
        b = s.encode("utf-8")
        head += struct.pack("<H", len(b)) + b
    head += struct.pack("<I", len(regions))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_bytes(bytes(head + body))
    print(f"{len(regions)} 个区域，{points} 个点，{OUT.stat().st_size / 1e6:.2f} MB → {OUT.relative_to(ROOT)}；匹配 {stats}")


if __name__ == "__main__":
    main()
