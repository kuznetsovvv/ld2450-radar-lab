import math


CONFIG_SCHEMA = "ld2450-radar-config/1"
EVENT_SCHEMA = "ld2450-radar-event/1"
UINT32_MODULUS = 1 << 32
ROLLOVER_HIGH_WATER = 0xF0000000
ROLLOVER_LOW_WATER = 0x0FFFFFFF
TIME_EPSILON_S = 1e-9


def make_runtime(config):
    validate_config(config)
    return {
        "config": config,
        "tracks": [],
        "next_id": 0,
        "previous_t_ms": None,
        "rollover_offset_ms": 0,
        "previous_t_s": None,
    }


def validate_config(config):
    if config.get("schema") != CONFIG_SCHEMA:
        raise ValueError("unsupported config schema")
    if config.get("coordinate_units") != "mm" or config.get("time_units") != "s":
        raise ValueError("version 1 requires millimetres and seconds")
    required_tracker = (
        "gate_mm",
        "max_coast_s",
        "measurement_sigma_mm",
        "acceleration_sigma_mm_s2",
        "initial_position_sigma_mm",
        "initial_velocity_sigma_mm_s",
        "min_confirmed_hits",
    )
    for key in required_tracker:
        if key not in config.get("tracker", {}):
            raise ValueError("missing tracker setting: " + key)
    names = []
    for portal in config.get("portals", []):
        name = portal.get("name")
        if not name or name in names:
            raise ValueError("portal names must be present and unique")
        names.append(name)
        if portal.get("shape") not in ("box", "sector"):
            raise ValueError("unsupported portal shape")


def process_payload(runtime, payload):
    t_ms, detections = _parse_payload(payload)
    clock_reset = False
    previous_t_ms = runtime["previous_t_ms"]
    if previous_t_ms is not None and t_ms < previous_t_ms:
        if previous_t_ms >= ROLLOVER_HIGH_WATER and t_ms <= ROLLOVER_LOW_WATER:
            runtime["rollover_offset_ms"] += UINT32_MODULUS
        else:
            clock_reset = True
    completed = []
    if clock_reset:
        completed.extend(flush_runtime(runtime))
        runtime["rollover_offset_ms"] = 0
    runtime["previous_t_ms"] = t_ms
    t_s = (runtime["rollover_offset_ms"] + t_ms) / 1000.0
    completed.extend(_update(runtime, t_s, detections))
    return completed, clock_reset


def flush_runtime(runtime):
    completed = []
    for track in runtime["tracks"]:
        if track["hits"] >= runtime["config"]["tracker"]["min_confirmed_hits"]:
            completed.append(_classify(runtime["config"], track))
    runtime["tracks"] = []
    runtime["previous_t_s"] = None
    return completed


def _parse_payload(payload):
    parts = payload.split("|")
    if len(parts) != 4:
        raise ValueError("payload must contain one timestamp and three target slots")
    t_ms = int(parts[0])
    if t_ms < 0 or t_ms >= UINT32_MODULUS:
        raise ValueError("timestamp must be an unsigned 32-bit value")
    detections = []
    slot = 1
    for segment in parts[1:]:
        values = segment.split(",")
        if len(values) != 3:
            raise ValueError("target slot must contain x,y,v")
        x_mm = int(values[0])
        y_mm = int(values[1])
        if x_mm != 0 or y_mm != 0:
            detections.append({"x": x_mm, "y": y_mm, "slot": slot})
        slot += 1
    return t_ms, detections


def _axis(position, position_variance, velocity_variance):
    return [position, 0.0, position_variance, 0.0, 0.0, velocity_variance]


def _predict_axis(axis, dt_s, acceleration_variance):
    axis[0] += axis[1] * dt_s
    p00 = axis[2] + dt_s * (axis[4] + axis[3]) + dt_s * dt_s * axis[5]
    p01 = axis[3] + dt_s * axis[5]
    p10 = axis[4] + dt_s * axis[5]
    p11 = axis[5]
    dt2 = dt_s * dt_s
    dt3 = dt2 * dt_s
    dt4 = dt2 * dt2
    axis[2] = p00 + acceleration_variance * dt4 / 4.0
    axis[3] = p01 + acceleration_variance * dt3 / 2.0
    axis[4] = p10 + acceleration_variance * dt3 / 2.0
    axis[5] = p11 + acceleration_variance * dt2


def _update_axis(axis, measurement, measurement_variance):
    innovation = measurement - axis[0]
    innovation_variance = axis[2] + measurement_variance
    gain_position = axis[2] / innovation_variance
    gain_velocity = axis[4] / innovation_variance
    old_p00 = axis[2]
    old_p01 = axis[3]
    axis[0] += gain_position * innovation
    axis[1] += gain_velocity * innovation
    axis[2] -= gain_position * old_p00
    axis[3] -= gain_position * old_p01
    axis[4] -= gain_velocity * old_p00
    axis[5] -= gain_velocity * old_p01
    cross = (axis[3] + axis[4]) / 2.0
    axis[3] = cross
    axis[4] = cross


def _assignment(tracks, detections, gate_mm):
    best = {"cost": None, "pairs": []}

    def visit(index, used, pairs, cost):
        if best["cost"] is not None and cost >= best["cost"]:
            return
        if index == len(detections):
            best["cost"] = cost
            best["pairs"] = list(pairs)
            return
        visit(index + 1, used, pairs, cost + gate_mm)
        detection = detections[index]
        track_index = 0
        for track in tracks:
            if track_index not in used:
                dx = detection["x"] - track["x"][0]
                dy = detection["y"] - track["y"][0]
                distance = (dx * dx + dy * dy) ** 0.5
                if distance < gate_mm:
                    used.append(track_index)
                    pairs.append((track_index, index))
                    visit(index + 1, used, pairs, cost + distance)
                    pairs.pop()
                    used.pop()
            track_index += 1

    visit(0, [], [], 0.0)
    return best["pairs"]


def _update(runtime, t_s, detections):
    config = runtime["config"]["tracker"]
    previous_t_s = runtime["previous_t_s"]
    if previous_t_s is not None and t_s <= previous_t_s:
        raise ValueError("frame timestamps must be strictly increasing")
    runtime["previous_t_s"] = t_s
    completed = []
    still_live = []
    for track in runtime["tracks"]:
        if t_s - track["last_seen"] <= config["max_coast_s"] + TIME_EPSILON_S:
            dt_s = t_s - track["state_t"]
            acceleration_variance = config["acceleration_sigma_mm_s2"] ** 2
            _predict_axis(track["x"], dt_s, acceleration_variance)
            _predict_axis(track["y"], dt_s, acceleration_variance)
            track["state_t"] = t_s
            still_live.append(track)
        elif track["hits"] >= config["min_confirmed_hits"]:
            completed.append(_classify(runtime["config"], track))
    runtime["tracks"] = still_live

    pairs = _assignment(runtime["tracks"], detections, config["gate_mm"])
    matched = []
    measurement_variance = config["measurement_sigma_mm"] ** 2
    for track_index, detection_index in pairs:
        track = runtime["tracks"][track_index]
        detection = detections[detection_index]
        _update_axis(track["x"], detection["x"], measurement_variance)
        _update_axis(track["y"], detection["y"], measurement_variance)
        track["points"].append([t_s, track["x"][0], track["y"][0], detection["slot"]])
        track["last_seen"] = t_s
        track["hits"] += 1
        matched.append(detection_index)

    detection_index = 0
    for detection in detections:
        if detection_index not in matched:
            position_variance = config["initial_position_sigma_mm"] ** 2
            velocity_variance = config["initial_velocity_sigma_mm_s"] ** 2
            runtime["tracks"].append(
                {
                    "id": runtime["next_id"],
                    "x": _axis(detection["x"], position_variance, velocity_variance),
                    "y": _axis(detection["y"], position_variance, velocity_variance),
                    "state_t": t_s,
                    "last_seen": t_s,
                    "hits": 1,
                    "points": [[t_s, detection["x"], detection["y"], detection["slot"]]],
                }
            )
            runtime["next_id"] += 1
        detection_index += 1
    return completed


def _median(values):
    ordered = sorted(values)
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[middle]
    return (ordered[middle - 1] + ordered[middle]) / 2.0


def _portal_matches(x_mm, y_mm, portals):
    matches = []
    for portal in portals:
        if portal["shape"] == "box":
            inside = (
                portal["min_x_mm"] <= x_mm <= portal["max_x_mm"]
                and portal["min_y_mm"] <= y_mm <= portal["max_y_mm"]
            )
        else:
            range_mm = (x_mm * x_mm + y_mm * y_mm) ** 0.5
            inside = False
            if portal["min_range_mm"] <= range_mm <= portal["max_range_mm"]:
                fraction = (range_mm - portal["min_range_mm"]) / (
                    portal["max_range_mm"] - portal["min_range_mm"]
                )
                min_angle = portal["near_min_angle_deg"] + fraction * (
                    portal["far_min_angle_deg"] - portal["near_min_angle_deg"]
                )
                max_angle = portal["near_max_angle_deg"] + fraction * (
                    portal["far_max_angle_deg"] - portal["near_max_angle_deg"]
                )
                angle = math.atan2(x_mm, y_mm) * 180.0 / math.pi
                inside = min_angle <= angle <= max_angle
        if inside:
            matches.append(portal["name"])
    return matches


def _classify(config, track):
    classifier = config["classifier"]
    count = min(classifier["endpoint_points"], len(track["points"]))
    start = track["points"][:count]
    end = track["points"][-count:]
    start_x = _median([point[1] for point in start])
    start_y = _median([point[2] for point in start])
    end_x = _median([point[1] for point in end])
    end_y = _median([point[2] for point in end])
    span_mm = ((end_x - start_x) ** 2 + (end_y - start_y) ** 2) ** 0.5
    origins = _portal_matches(start_x, start_y, config["portals"])
    destinations = _portal_matches(end_x, end_y, config["portals"])
    origin = origins[0] if len(origins) == 1 else None
    destination = destinations[0] if len(destinations) == 1 else None
    if span_mm < classifier["min_span_mm"]:
        confidence = "low"
        reason = "short_track"
    elif len(origins) > 1 or len(destinations) > 1:
        confidence = "low"
        reason = "overlapping_portals"
    elif origin is None or destination is None:
        confidence = "low"
        reason = "unmatched_endpoint"
    else:
        confidence = "medium"
        reason = "endpoint_portals"
    return {
        "schema": EVENT_SCHEMA,
        "track_id": track["id"],
        "origin": origin,
        "destination": destination,
        "label": (origin or "UNKNOWN") + "->" + (destination or "UNKNOWN"),
        "confidence": confidence,
        "reason": reason,
        "span_mm": round(span_mm, 1),
        "point_count": len(track["points"]),
    }