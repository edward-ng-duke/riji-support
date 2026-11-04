# 日拾离线地名数据库

这里提供日拾分发的完整衍生地名数据库、上游署名、许可文本和转换脚本。数据发布于 2026 年 11 月 4 日。

## 下载与许可

- `places-cn.bin` 是完整离线边界和中文地名数据库，采用可完整解码的 RJPL v1 格式。
- `administrative-places.json` 是从同一数据库生成的行政名称白名单。
- `manifest.json` 记录文件大小、SHA-256、来源版本和修改方式。

本衍生数据库依据 Open Data Commons Open Database License 1.0 提供。你可以依据该许可共享、修改和使用数据库，并履行署名及相同方式共享等适用义务。完整许可文本随数据提供。[ODbL 1.0](licenses/ODbL-1.0.html)

数据库中的 GeoNames 来源同时保留其 CC BY 4.0 署名和适用权利。转换脚本的许可单独列于 `scripts/LICENSE`。[CC BY 4.0](licenses/CC-BY-4.0.txt)

## 数据署名与来源

- © OpenStreetMap contributors。区县边界采用 geoBoundaries CHN ADM3，来源元数据列明 Lee Beryman、OpenStreetMap，边界标识为 `CHN-ADM3-62558664`，上游许可为 ODbL 1.0。固定来源提交为 `9469f09`。[geoBoundaries ADM3](https://github.com/wmgeolab/geoBoundaries/tree/9469f09/releaseData/gbOpen/CHN/ADM3) [OpenStreetMap 版权与许可](https://www.openstreetmap.org/copyright)
- geoBoundaries，William & Mary geoLab 及贡献者。省级兜底边界采用同一提交中的 CHN ADM1，边界标识为 `CHN-ADM1-43563684`。上游元数据标为 Public Domain，来源列为 geoBoundaries、Wikimedia Commons。[geoBoundaries ADM1](https://github.com/wmgeolab/geoBoundaries/tree/9469f09/releaseData/gbOpen/CHN/ADM1)
- © GeoNames 及其贡献者。中文行政名称和上级市、省匹配来自 GeoNames `CN.zip`，其下载说明规定 CC BY 4.0。原始构建未记录该可变下载源的快照日期，本次完整发布已经分发的衍生数据库。[GeoNames 下载](https://download.geonames.org/export/dump/) [GeoNames 许可](https://www.geonames.org/export/)

上游元数据和下载说明保存在 `sources/`。边界和地名可能包含历史名称、匹配误差或简化误差，适用于日拾的粗略地点标签。

## 已作的修改

1. 用 GeoNames 中文行政名称及上级市、省信息匹配 geoBoundaries 边界，并对少量名称作选择与去重。
2. 对多边形实施 Douglas–Peucker 简化，容差为 0.003 度，约 300 米。
3. 将中文名称、包围盒和边界坐标编码为 RJPL v1 二进制数据库。
4. 将匹配不到区县时使用的省级边界作为兜底条目保留。
5. 从完整数据库提取行政名称白名单，删除不符合白名单规则的镇级名称。

## 完整解码

使用 Python 3，无额外依赖，运行以下命令可以把已分发的完整数据库转换为通用 GeoJSON。输出包含全部边界、中文名称和省级兜底标记。

```sh
python3 scripts/decode_places.py places-cn.bin places-cn.geojson
```

## 重新生成

准备一个上游数据目录 `upstream/`，将固定提交中的 `geoBoundaries-CHN-ADM3_simplified.geojson` 保存为 `CHN_ADM3.geojson`，将 `geoBoundaries-CHN-ADM1_simplified.geojson` 保存为 `CHN_ADM1.geojson`，再将 GeoNames `CN.zip` 解压得到的 `CN.txt` 放入该目录。GitHub 数据文件可能使用 Git LFS，下载时应获取实际文件内容。

```sh
python3 scripts/build_places.py upstream/
python3 scripts/build_ai_place_names.py
```

两个脚本仅把原项目输出路径调整为本公开数据目录，转换算法保持原样。使用更新后的 GeoNames 快照可能生成不同结果，当前分发数据的确切内容以下载文件及 `manifest.json` 的校验值为准。

## RJPL v1 格式

所有整数和浮点数采用小端字节序。坐标采用 float32。

1. 文件头为 ASCII `RJPL`，随后是 uint16 版本号 `1`。
2. uint32 字符串数量，随后逐项为 uint16 UTF-8 字节长度和对应名称字节。
3. uint32 区域数量，随后逐项为区域记录。
4. 区域记录依次为 uint16 区县名称索引、uint16 上级市名称索引、uint8 省级兜底标记、4 个 float32 包围盒数值和 uint16 环数量。上级市索引 `65535` 表示无值。
5. 每个环依次为 uint8 内环标记、uint32 点数量和逐点的 2 个 float32 经度、纬度。一个外环及其后续内环构成一个多边形。

数据包与应用独立公开提供，可直接下载并按所附数据许可使用。
