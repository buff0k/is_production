import json

import numpy as np
from shapely.geometry import Polygon, Point, box, LineString, mapping
from shapely.ops import polygonize, unary_union
from shapely import affinity


def _float(value, default=0.0):
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def _int(value, default=0):
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def clean_xy_points(points):
    clean = []
    for idx, p in enumerate(points or []):
        try:
            x = float(p.get("x"))
            y = float(p.get("y"))
            z = _float(p.get("z"), 0.0)
        except Exception:
            continue
        clean.append({"x": x, "y": y, "z": z, "row_no": _int(p.get("row_no"), idx + 1), "raw": p})
    return clean


def _median_gap(values, fallback=20.0):
    values = sorted(set(round(float(v), 6) for v in values if v is not None))
    gaps = []
    for i in range(1, len(values)):
        gap = values[i] - values[i - 1]
        if gap > 0.000001:
            gaps.append(gap)
    if not gaps:
        return fallback
    gaps.sort()
    return gaps[len(gaps) // 2]


def estimate_mesh_size(points, fallback_x=20.0, fallback_y=20.0):
    clean = clean_xy_points(points)
    if len(clean) < 2:
        return fallback_x, fallback_y
    return _median_gap([p["x"] for p in clean], fallback_x), _median_gap([p["y"] for p in clean], fallback_y)


def _edge_key(a, b):
    return (round(a[0], 4), round(a[1], 4), round(b[0], 4), round(b[1], 4))


def _grid_coverage_polygon(points):
    clean = clean_xy_points(points)
    if len(clean) < 3:
        return None

    cell_x, cell_y = estimate_mesh_size(clean, 20.0, 20.0)
    half_x = cell_x / 2.0
    half_y = cell_y / 2.0
    edge_map = {}

    def add_or_remove(a, b):
        key_ab = _edge_key(a, b)
        key_ba = _edge_key(b, a)
        if key_ba in edge_map:
            del edge_map[key_ba]
        else:
            edge_map[key_ab] = (a, b)

    for p in clean:
        x = p["x"]
        y = p["y"]
        p1 = (x - half_x, y - half_y)
        p2 = (x + half_x, y - half_y)
        p3 = (x + half_x, y + half_y)
        p4 = (x - half_x, y + half_y)
        add_or_remove(p1, p2)
        add_or_remove(p2, p3)
        add_or_remove(p3, p4)
        add_or_remove(p4, p1)

    lines = [LineString([a, b]) for a, b in edge_map.values()]
    if not lines:
        return None

    polygons = list(polygonize(lines))
    if not polygons:
        return None

    geom = unary_union(polygons)
    if not geom.is_valid:
        geom = geom.buffer(0)
    return None if geom.is_empty else geom


def build_pit_geometry(pit_points):
    clean = clean_xy_points(pit_points)
    if len(clean) < 3:
        return None

    if len(clean) > 200:
        return _grid_coverage_polygon(clean)

    clean = sorted(clean, key=lambda p: p.get("row_no") or 0)
    polygon = Polygon([(p["x"], p["y"]) for p in clean])
    if not polygon.is_valid:
        polygon = polygon.buffer(0)
    return None if polygon.is_empty else polygon


def _largest_polygon(geom):
    if geom is None or geom.is_empty:
        return None
    if geom.geom_type == "Polygon":
        return geom
    if geom.geom_type == "MultiPolygon":
        return max(list(geom.geoms), key=lambda g: g.area)
    return None


def _polygon_corners(polygon):
    polygon = _largest_polygon(polygon)
    if polygon is None:
        return []
    coords = list(polygon.exterior.coords)
    if len(coords) > 1 and coords[0] == coords[-1]:
        coords = coords[:-1]
    return [{"x": float(x), "y": float(y)} for x, y in coords]


def _geometry_to_geojson(geom):
    if geom is None or geom.is_empty:
        return ""
    return json.dumps(mapping(geom))


def generate_layout_blocks_from_pit(
    pit_points,
    block_size_x=100,
    block_size_y=40,
    angle_degrees=0,
    minimum_inside_percent=50,
    cut_no=1,
    numbering_style="C1B1",
):
    block_size_x = _float(block_size_x, 100.0)
    block_size_y = _float(block_size_y, 40.0)
    angle_degrees = _float(angle_degrees, 0.0)
    minimum_inside_percent = _float(minimum_inside_percent, 50.0)
    cut_no = _int(cut_no, 1)

    if block_size_x <= 0 or block_size_y <= 0:
        raise ValueError("Block Size X and Block Size Y must be greater than zero.")

    pit_geom = build_pit_geometry(pit_points)
    if pit_geom is None or pit_geom.is_empty:
        raise ValueError("Could not build a valid pit polygon from the selected pit outline points.")

    minx, miny, maxx, maxy = pit_geom.bounds
    base_polygon = _largest_polygon(pit_geom)
    origin = base_polygon.centroid if base_polygon else Point(minx, miny)

    pad = max(block_size_x, block_size_y) * 2.0
    minx -= pad
    miny -= pad
    maxx += pad
    maxy += pad

    blocks = []
    block_no = 0

    y_values = np.arange(miny, maxy + block_size_y, block_size_y)
    x_values = np.arange(minx, maxx + block_size_x, block_size_x)

    for row_no, y in enumerate(y_values, start=1):
        for column_no, x in enumerate(x_values, start=1):
            raw_block = box(x, y, x + block_size_x, y + block_size_y)

            if angle_degrees:
                raw_block = affinity.rotate(raw_block, angle_degrees, origin=origin, use_radians=False)

            effective = raw_block.intersection(pit_geom)
            effective = _largest_polygon(effective)

            if effective is None or effective.is_empty or effective.area <= 0:
                continue

            inside_percent = (effective.area / raw_block.area) * 100.0 if raw_block.area else 0
            if inside_percent < minimum_inside_percent:
                continue

            block_no += 1

            if numbering_style == "Row Column":
                block_code = f"R{row_no}C{column_no}"
            else:
                block_code = f"C{cut_no}B{block_no}"

            blocks.append({
                "block_code": block_code,
                "cut_no": cut_no,
                "block_no": block_no,
                "row_no": row_no,
                "column_no": column_no,
                "centroid_x": float(effective.centroid.x),
                "centroid_y": float(effective.centroid.y),
                "block_size_x": block_size_x,
                "block_size_y": block_size_y,
                "angle_degrees": angle_degrees,
                "area": float(raw_block.area),
                "effective_area": float(effective.area),
                "inside_percent": float(inside_percent),
                "polygon_geojson": _geometry_to_geojson(effective),
                "corners_json": json.dumps(_polygon_corners(effective)),
                "block_status": "Draft",
            })

    return blocks
