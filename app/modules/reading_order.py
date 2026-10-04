from dataclasses import dataclass
from statistics import median

from app.ocr.base import TextBox

GUTTER_MIN_WIDTH_RATIO = 0.025
GUTTER_COVERAGE_LIMIT = 0.06
LINE_OVERLAP_RATIO = 0.5
PARAGRAPH_GAP_FACTOR = 1.6
HEADING_HEIGHT_FACTOR = 1.35
MIN_COLUMN_BOXES = 3
WIDE_BOX_RATIO = 0.55


@dataclass(frozen=True)
class Line:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def height(self) -> float:
        return max(self.y1 - self.y0, 1.0)


@dataclass(frozen=True)
class Block:
    lines: list[Line]
    heading: bool


@dataclass(frozen=True)
class PageLayout:
    columns: int
    blocks: list[Block]

    @property
    def text(self) -> str:
        return "\n\n".join(" ".join(line.text for line in block.lines) for block in self.blocks)

    def markdown(self) -> str:
        parts = []
        for block in self.blocks:
            content = " ".join(line.text for line in block.lines)
            parts.append(f"## {content}" if block.heading else content)
        return "\n\n".join(parts)

    def as_dict(self) -> dict:
        return {
            "columns": self.columns,
            "blocks": [{"heading": block.heading, "lines": [line.text for line in block.lines]} for block in self.blocks],
        }


def find_gutters(boxes: list[TextBox]) -> list[float]:
    if not boxes:
        return []
    left = min(box.x0 for box in boxes)
    extent = max(box.x1 for box in boxes) - left
    if extent <= 0:
        return []
    resolution = 400
    coverage = [0.0] * resolution
    total_height = sum(box.height for box in boxes)
    for box in boxes:
        start = max(0, int((box.x0 - left) / extent * resolution))
        end = min(resolution, int((box.x1 - left) / extent * resolution) + 1)
        for index in range(start, end):
            coverage[index] += box.height
    threshold = total_height * GUTTER_COVERAGE_LIMIT
    gutters, run_start = [], None
    minimum_run = max(2, int(resolution * GUTTER_MIN_WIDTH_RATIO))
    for index in range(1, resolution - 1):
        if coverage[index] <= threshold:
            run_start = index if run_start is None else run_start
        elif run_start is not None:
            if index - run_start >= minimum_run:
                gutters.append(left + (run_start + index) / 2 / resolution * extent)
            run_start = None
    return gutters


def split_columns(boxes: list[TextBox], gutters: list[float]) -> list[list[TextBox]]:
    edges = [float("-inf"), *gutters, float("inf")]
    columns = [[box for box in boxes if edges[index] <= box.center_x < edges[index + 1]] for index in range(len(edges) - 1)]
    if any(len(column) < MIN_COLUMN_BOXES for column in columns) and len(columns) > 1:
        return [boxes]
    return columns


def group_lines(boxes: list[TextBox]) -> list[Line]:
    lines: list[list[TextBox]] = []
    for box in sorted(boxes, key=lambda item: (item.center_y, item.x0)):
        for line in lines:
            reference = line[-1]
            overlap = min(reference.y1, box.y1) - max(reference.y0, box.y0)
            if overlap >= LINE_OVERLAP_RATIO * min(reference.height, box.height):
                line.append(box)
                break
        else:
            lines.append([box])
    result = []
    for line in lines:
        ordered = sorted(line, key=lambda item: item.x0)
        result.append(
            Line(
                " ".join(box.text for box in ordered),
                min(box.x0 for box in ordered),
                min(box.y0 for box in ordered),
                max(box.x1 for box in ordered),
                max(box.y1 for box in ordered),
            )
        )
    return sorted(result, key=lambda line: line.y0)


def group_blocks(lines: list[Line], typical_height: float) -> list[Block]:
    blocks: list[Block] = []
    current: list[Line] = []
    for line in lines:
        heading = line.height >= typical_height * HEADING_HEIGHT_FACTOR
        if current:
            gap = line.y0 - current[-1].y1
            previous_heading = current[-1].height >= typical_height * HEADING_HEIGHT_FACTOR
            if gap > typical_height * PARAGRAPH_GAP_FACTOR or heading != previous_heading:
                blocks.append(Block(current, previous_heading))
                current = []
        current.append(line)
    if current:
        blocks.append(Block(current, current[-1].height >= typical_height * HEADING_HEIGHT_FACTOR))
    return blocks


def crosses(box: TextBox, gutters: list[float]) -> bool:
    return any(box.x0 < gutter < box.x1 for gutter in gutters)


def analyze_layout(boxes: list[TextBox]) -> PageLayout:
    if not boxes:
        return PageLayout(0, [])
    typical_height = median(box.height for box in boxes)
    extent = max(box.x1 for box in boxes) - min(box.x0 for box in boxes)
    narrow = [box for box in boxes if box.x1 - box.x0 <= extent * WIDE_BOX_RATIO]
    gutters = find_gutters(narrow)
    spanning = sorted((box for box in boxes if crosses(box, gutters)), key=lambda item: item.y0) if gutters else []
    flowing = [box for box in boxes if box not in spanning]
    columns = split_columns(flowing, gutters) if gutters else [flowing]
    blocks: list[Block] = []
    emitted: set[int] = set()
    for separator in [*spanning, None]:
        limit = separator.y0 if separator else float("inf")
        for column in columns:
            section = [box for box in column if id(box) not in emitted and box.center_y < limit]
            emitted.update(id(box) for box in section)
            blocks.extend(group_blocks(group_lines(section), typical_height))
        if separator:
            blocks.extend(group_blocks(group_lines([separator]), typical_height))
    return PageLayout(max(len(columns), 1), blocks)
