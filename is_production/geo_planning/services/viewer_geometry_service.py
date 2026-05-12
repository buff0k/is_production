import numpy as np
from shapely.geometry import Polygon, Point, box, LineString, mapping
from shapely import affinity
from shapely.ops import polygonize, unary_union


DEFAULT_BLOCK_SIZE_X = 100
DEFAULT_BLOCK_SIZE_Y = 40
DEFAULT_MESH_SIZE_X = 20
DEFAULT_MESH_SIZE_Y = 20
DEFAULT_MINIMUM_INSIDE_PERCENT = 50
DEFAULT_CUT_NO = 1
EPSILON = 0.000001


def _float(value, default=0):
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


def _clean_points(points):
	clean = []

	for index, p in enumerate(points or []):
		try:
			x = float(p.get("x"))
			y = float(p.get("y"))
			z = float(p.get("z", 0) or 0)
		except Exception:
			continue

		clean.append({
			"x": x,
			"y": y,
			"z": z,
			"row_no": _int(p.get("row_no"), index + 1),
			"raw": p,
		})

	return clean


def _median_gap(values, fallback):
	values = sorted(set(round(float(v), 6) for v in values if v is not None))
	gaps = [
		values[i] - values[i - 1]
		for i in range(1, len(values))
		if values[i] - values[i - 1] > EPSILON
	]

	if not gaps:
		return fallback

	gaps.sort()
	return gaps[len(gaps) // 2]


def _estimate_mesh_size(points, fallback_x=DEFAULT_MESH_SIZE_X, fallback_y=DEFAULT_MESH_SIZE_Y):
	clean = _clean_points(points)

	if len(clean) < 2:
		return fallback_x, fallback_y

	return (
		_median_gap((p["x"] for p in clean), fallback_x),
		_median_gap((p["y"] for p in clean), fallback_y),
	)


def _bounds_from_points(points):
	clean = _clean_points(points)

	if not clean:
		return None

	xs = [p["x"] for p in clean]
	ys = [p["y"] for p in clean]

	return min(xs), min(ys), max(xs), max(ys)


def _edge_key(a, b):
	return (
		round(a[0], 4),
		round(a[1], 4),
		round(b[0], 4),
		round(b[1], 4),
	)


def _grid_coverage_polygon(points):
	"""
	Build a pit/model coverage polygon from grid/cell-centre points.

	This is designed for your Pit Outline Points case, where the batch may contain
	thousands of points representing occupied cells rather than one simple closed
	polygon string.
	"""
	clean = _clean_points(points)

	if len(clean) < 3:
		return None

	cell_x, cell_y = _estimate_mesh_size(clean, DEFAULT_MESH_SIZE_X, DEFAULT_MESH_SIZE_Y)
	half_x = cell_x / 2
	half_y = cell_y / 2
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

	poly = unary_union(polygons)

	if not poly.is_valid:
		poly = poly.buffer(0)

	if poly.is_empty:
		return None

	return poly


def points_to_pit_polygon(pit_points):
	"""
	Convert pit points into a geometry.

	Small ordered point sets are treated as a closed polygon.
	Large grid-style pit point sets are converted into a coverage polygon.
	"""
	clean = _clean_points(pit_points)

	if len(clean) < 3:
		return None

	# Large pit batches are usually cell/grid points, not ordered outline vertices.
	if len(clean) > 200:
		return _grid_coverage_polygon(clean)

	clean = sorted(clean, key=lambda p: p.get("row_no") or 0)
	polygon = Polygon((p["x"], p["y"]) for p in clean)

	if not polygon.is_valid:
		polygon = polygon.buffer(0)

	if polygon.is_empty:
		return None

	return polygon


def _largest_polygon(geom):
	if geom is None or geom.is_empty:
		return None

	if geom.geom_type == "Polygon":
		return geom

	if geom.geom_type == "MultiPolygon":
		return max(geom.geoms, key=lambda g: g.area)

	return None


def _polygon_corners_for_viewer(polygon):
	polygon = _largest_polygon(polygon)

	if polygon is None:
		return []

	coords = list(polygon.exterior.coords)

	if len(coords) > 1 and coords[0] == coords[-1]:
		coords = coords[:-1]

	return [{"x": float(x), "y": float(y)} for x, y in coords]


def _points_inside_polygon(points, polygon):
	"""
	Simple bounded point-in-polygon lookup.

	This is intentionally dependency-light. It first filters by polygon bounds so
	it is much faster than testing every point against every block blindly.
	"""
	minx, miny, maxx, maxy = polygon.bounds
	inside = []

	for p in points:
		x = p["x"]
		y = p["y"]

		if x < minx or x > maxx or y < miny or y > maxy:
			continue

		try:
			pt = Point(x, y)

			if polygon.contains(pt) or polygon.touches(pt):
				inside.append(p)
		except Exception:
			continue

	return inside


def _get_generation_bounds(clean_points, clean_pit_points, block_size_x, block_size_y):
	pit_polygon = points_to_pit_polygon(clean_pit_points)

	if pit_polygon:
		minx, miny, maxx, maxy = pit_polygon.bounds
		base_polygon = _largest_polygon(pit_polygon)
		origin = base_polygon.centroid if base_polygon else Point(minx, miny)
	else:
		bounds = _bounds_from_points(clean_points)

		if not bounds:
			return None, None

		minx, miny, maxx, maxy = bounds
		origin = Point(minx, miny)

	pad = max(block_size_x, block_size_y) * 2
	return (minx - pad, miny - pad, maxx + pad, maxy + pad), (pit_polygon, origin)


def _z_summary(block_points):
	z_values = [p["z"] for p in block_points]

	if not z_values:
		return 0, 0, 0

	return (
		float(sum(z_values) / len(z_values)),
		float(min(z_values)),
		float(max(z_values)),
	)


def generate_preview_blocks(
	points,
	pit_points=None,
	block_size_x=DEFAULT_BLOCK_SIZE_X,
	block_size_y=DEFAULT_BLOCK_SIZE_Y,
	mesh_size_x=None,
	mesh_size_y=None,
	angle_degrees=0,
	minimum_inside_percent=DEFAULT_MINIMUM_INSIDE_PERCENT,
	auto_number_blocks=0,
	cut_no=DEFAULT_CUT_NO,
	**kwargs
):
	"""
	Backend mining block generation for Geo Planning Viewer.

	The viewer sends filters only. geo_planning_viewer.py loads the matching
	DocType rows and passes them here. This function then uses Shapely/Numpy to
	generate accurate preview block geometry.
	"""
	clean_points = _clean_points(points)
	clean_pit_points = _clean_points(pit_points or [])

	if not clean_points and not clean_pit_points:
		return []

	block_size_x = _float(block_size_x, DEFAULT_BLOCK_SIZE_X)
	block_size_y = _float(block_size_y, DEFAULT_BLOCK_SIZE_Y)
	mesh_size_x = _float(mesh_size_x, 0)
	mesh_size_y = _float(mesh_size_y, 0)
	angle_degrees = _float(angle_degrees, 0)
	minimum_inside_percent = _float(minimum_inside_percent, DEFAULT_MINIMUM_INSIDE_PERCENT)
	auto_number_blocks = _int(auto_number_blocks, 0)
	cut_no = _int(cut_no, DEFAULT_CUT_NO)

	if block_size_x <= 0 or block_size_y <= 0:
		return []

	if mesh_size_x <= 0 or mesh_size_y <= 0:
		mesh_size_x, mesh_size_y = _estimate_mesh_size(clean_points, DEFAULT_MESH_SIZE_X, DEFAULT_MESH_SIZE_Y)

	expected_point_count = max(
		1,
		int(round((block_size_x / mesh_size_x) * (block_size_y / mesh_size_y)))
	)

	bounds, geometry_info = _get_generation_bounds(
		clean_points,
		clean_pit_points,
		block_size_x,
		block_size_y,
	)

	if not bounds:
		return []

	minx, miny, maxx, maxy = bounds
	pit_polygon, origin = geometry_info

	blocks = []
	block_no = 0

	y_values = np.arange(miny, maxy + block_size_y, block_size_y)
	x_values = np.arange(minx, maxx + block_size_x, block_size_x)

	for row_no, y in enumerate(y_values, start=1):
		for col_no, x in enumerate(x_values, start=1):
			raw_block = box(x, y, x + block_size_x, y + block_size_y)

			if angle_degrees:
				raw_block = affinity.rotate(
					raw_block,
					angle_degrees,
					origin=origin,
					use_radians=False,
				)

			effective = raw_block.intersection(pit_polygon) if pit_polygon else raw_block
			effective = _largest_polygon(effective)

			if effective is None or effective.is_empty or effective.area <= 0:
				continue

			inside_percent = (effective.area / raw_block.area) * 100 if raw_block.area else 0

			if inside_percent < minimum_inside_percent:
				continue

			block_points = _points_inside_polygon(clean_points, effective)

			# Without a pit outline, do not create empty model blocks.
			if not pit_polygon and not block_points:
				continue

			block_no += 1

			label = f"C{cut_no}B{block_no}" if auto_number_blocks else ""
			avg_z, min_z, max_z = _z_summary(block_points)
			corners = _polygon_corners_for_viewer(effective)

			blocks.append({
				"cut_no": cut_no,
				"block_no": block_no if auto_number_blocks else 0,
				"label": label,
				"key": f"{col_no}|{row_no}",
				"row": row_no,
				"col": col_no,
				"x": float(effective.centroid.x),
				"y": float(effective.centroid.y),
				"width": block_size_x,
				"height": block_size_y,
				"angle_degrees": angle_degrees,
				"area": float(raw_block.area),
				"effective_area": float(effective.area),
				"inside_percent": float(inside_percent),
				"point_count": len(block_points),
				"expected_point_count": expected_point_count,
				"avg_z": avg_z,
				"min_z": min_z,
				"max_z": max_z,
				"status": "Full Block" if inside_percent >= 99 else "Partial Block",
				"polygon_geojson": mapping(effective),
				"corners": corners,
				"anchor": {
					"x": float(origin.x),
					"y": float(origin.y),
				},
			})

	return blocks
