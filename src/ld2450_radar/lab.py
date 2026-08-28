from __future__ import annotations

import argparse
import json
import webbrowser
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from typing import Any
from urllib.parse import unquote

from .classification import classify_track
from .contract import RadarConfig
from .ingest import AtomicDataset, parse_atomic_csv
from .model import Frame
from .synthetic import default_config, demo_frames
from .tracker import track_frames


def _track_dict(track: Any) -> dict[str, object]:
    return {
        "id": track.id,
        "confirmed": track.confirmed,
        "points": [
            {
                "t_s": point.t_s,
                "observed_x_mm": point.observed_x_mm,
                "observed_y_mm": point.observed_y_mm,
                "filtered_x_mm": point.filtered_x_mm,
                "filtered_y_mm": point.filtered_y_mm,
                "velocity_x_mm_s": point.velocity_x_mm_s,
                "velocity_y_mm_s": point.velocity_y_mm_s,
                "source_slot": point.source_slot,
            }
            for point in track.points
        ],
    }


MAX_UPLOAD_BYTES = 25 * 1024 * 1024


def evaluate_config(
    config: RadarConfig,
    epochs: tuple[tuple[Frame, ...], ...] | None = None,
    source_name: str = "Synthetic demo",
) -> dict[str, object]:
    selected_epochs = epochs or (tuple(demo_frames()),)
    tracks = []
    next_track_id = 0
    for epoch in selected_epochs:
        epoch_tracks = track_frames(list(epoch), config.tracker)
        for track in epoch_tracks:
            track.id = next_track_id
            next_track_id += 1
            tracks.append(track)
    labels = [classify_track(track, config.portals, config.classifier) for track in tracks]
    return {
        "config": config.to_dict(),
        "tracks": [_track_dict(track) for track in tracks],
        "labels": [
            {
                "track_id": label.track_id,
                "label": label.label,
                "origin": label.origin,
                "destination": label.destination,
                "confidence": label.confidence,
                "reason": label.reason,
                "span_mm": round(label.span_mm, 1),
                "point_count": label.point_count,
            }
            for label in labels
        ],
        "summary": {
            "source_name": source_name,
            "frame_count": sum(len(epoch) for epoch in selected_epochs),
            "epoch_count": len(selected_epochs),
            "track_count": len(tracks),
            "classified_count": sum(
                label.origin is not None and label.destination is not None
                for label in labels
            ),
        },
    }


class LabState:
    def __init__(self) -> None:
        self.config = default_config()
        self.epochs = (tuple(demo_frames()),)
        self.source_name = "Synthetic demo"

    def evaluate(self) -> dict[str, object]:
        return evaluate_config(self.config, self.epochs, self.source_name)

    def update(self, value: dict[str, Any]) -> dict[str, object]:
        self.config = RadarConfig.from_dict(value)
        return self.evaluate()

    def reset(self) -> dict[str, object]:
        self.config = default_config()
        return self.evaluate()

    def use_demo(self) -> dict[str, object]:
        self.epochs = (tuple(demo_frames()),)
        self.source_name = "Synthetic demo"
        return self.evaluate()

    def load_csv(self, text: str, source_name: str) -> dict[str, object]:
        dataset: AtomicDataset = parse_atomic_csv(text)
        self.epochs = dataset.epochs
        self.source_name = source_name or "Uploaded atomic CSV"
        return self.evaluate()


class LabHandler(BaseHTTPRequestHandler):
    state: LabState

    def do_GET(self) -> None:
        if self.path == "/api/state":
            self._json(self.state.evaluate())
            return
        path = "index.html" if self.path in ("/", "/index.html") else self.path.lstrip("/")
        if path not in {"index.html", "app.js", "styles.css"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return
        resource = files("ld2450_radar").joinpath("web", path)
        content = resource.read_bytes()
        content_type = {
            "index.html": "text/html; charset=utf-8",
            "app.js": "text/javascript; charset=utf-8",
            "styles.css": "text/css; charset=utf-8",
        }[path]
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self) -> None:
        try:
            if self.path == "/api/config":
                self._json(self.state.update(self._request_json()))
                return
            if self.path == "/api/reset":
                self._json(self.state.reset())
                return
            if self.path == "/api/demo":
                self._json(self.state.use_demo())
                return
            if self.path == "/api/frames":
                content = self._request_bytes(MAX_UPLOAD_BYTES).decode("utf-8-sig")
                name = unquote(self.headers.get("X-File-Name", ""))
                self._json(self.state.load_csv(content, name))
                return
            self.send_error(HTTPStatus.NOT_FOUND)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
            self._json({"error": str(error)}, status=HTTPStatus.BAD_REQUEST)

    def log_message(self, format: str, *args: object) -> None:
        return

    def _request_json(self) -> dict[str, Any]:
        value = json.loads(self._request_bytes(MAX_UPLOAD_BYTES).decode("utf-8"))
        if not isinstance(value, dict):
            raise ValueError("request body must be an object")
        return value

    def _request_bytes(self, maximum: int) -> bytes:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            raise ValueError("request body is empty")
        if length > maximum:
            raise ValueError(f"request exceeds the {maximum // (1024 * 1024)} MB limit")
        return self.rfile.read(length)

    def _json(self, value: object, status: HTTPStatus = HTTPStatus.OK) -> None:
        content = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)


def serve(host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    state = LabState()
    handler = type("ConfiguredLabHandler", (LabHandler,), {"state": state})
    return ThreadingHTTPServer((host, port), handler)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local LD2450 radar tuning lab")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    server = serve(args.host, args.port)
    url = f"http://{args.host}:{args.port}"
    print(f"LD2450 Radar Lab: {url}")
    if not args.no_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()