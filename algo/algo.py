# algo.py
import json
import math
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class PaperSet(Enum):
    A = "A"
    B = "B"


@dataclass
class Seat:
    row: int
    col: int
    batch: Optional[int] = None
    paper_set: Optional[PaperSet] = None
    block: Optional[int] = None
    # roll_number may be an integer or a formatted string (e.g. BTCS24O1134 or enrollment)
    roll_number: Optional[str] = None
    # is_broken: True if this seat is broken/unavailable
    is_broken: bool = False
    # color: color code for display (e.g., "#FF0000" for red, "#F3F4F6" for light gray)
    color: str = "#FFFFFF"


class SeatingAlgorithm:
    # Default batch colors (can be customized)
    DEFAULT_BATCH_COLORS = {
        1: "#DBEAFE",  # Light blue
        2: "#DCFCE7",  # Light green
        3: "#FEE2E2",  # Light red/pink
        4: "#FEF3C7",  # Light yellow
        5: "#E9D5FF",  # Light purple
    }

    def __init__(
        self,
        rows: int,
        cols: int,
        num_batches: int,
        block_width: int = 3,
        batch_by_column: bool = True,
        enforce_no_adjacent_batches: bool = False,
        # roll formatting options
        roll_template: Optional[str] = None,
        batch_prefixes: Optional[Dict[int, str]] = None,
        year: Optional[int] = None,
        # sensible defaults: 1001 as starting serial and 4-digit serial width
        start_serial: int = 1001,
        start_serials: Optional[Dict[int, int]] = None,
        # Allow users to provide start roll strings per-batch e.g. {1: 'BTCS24O1135'}
        start_rolls: Optional[Dict[int, str]] = None,
        serial_width: int = 4,
        serial_mode: str = "per_batch",
        broken_seats: Optional[List[Tuple[int, int]]] = None,
        # batch student counts: {1: 35, 2: 30, 3: 25} etc
        batch_student_counts: Optional[Dict[int, int]] = None,
        # batch colors: {1: "#DBEAFE", 2: "#DCFCE7"} etc
        batch_colors: Optional[Dict[int, str]] = None,
        # NEW: human-readable labels for batches (e.g. branches) {1: "CSE", 2: "ECE"}
        batch_labels: Optional[Dict[int, str]] = None,
        # NEW: real enrollment numbers per batch.
        # Example: {1: ["BTCS24O1001", "BTCS24O1002"], 2: ["BTCD24O2001", ...]}
        batch_roll_numbers: Optional[Dict[int, List[str]]] = None,
    ):
        """
        rows, cols, num_batches: as before
        block_width: number of columns per block (default 3 as requested)
        batch_by_column: if True, assign each column to a batch and fill that column
                         top->down using that batch's roll-number pool (matches your example)
        enforce_no_adjacent_batches: when True validate that adjacent seats don't share same batch
        broken_seats: list of (row, col) tuples for seats that are broken/unavailable
        batch_student_counts: dict mapping batch number to total students in that batch
                            e.g. {1: 35, 2: 30, 3: 25} - determines how many from each batch to seat
        batch_colors: dict mapping batch number to color code (hex)
                     e.g. {1: "#DBEAFE", 2: "#DCFCE7"}
        batch_labels: dict mapping batch number to human-readable label (e.g. branch names)
                     e.g. {1: "CSE", 2: "ECE"}
        batch_roll_numbers: OPTIONAL: if provided, these are the actual roll/enrollment numbers
                            used instead of auto-generated serials.
        """
        self.rows = rows
        self.cols = cols
        self.num_batches = num_batches
        self.block_width = max(1, block_width)
        # number of blocks across the columns
        self.blocks = math.ceil(cols / self.block_width)
        self.batch_by_column = batch_by_column
        self.enforce_no_adjacent_batches = enforce_no_adjacent_batches
        # broken seats as a set for O(1) lookup
        self.broken_seats = set(broken_seats) if broken_seats else set()
        # batch student counts - total students available per batch
        self.batch_student_counts = batch_student_counts or {}
        # batch colors - use provided or fall back to defaults
        self.batch_colors = batch_colors or {}
        for b in range(1, num_batches + 1):
            if b not in self.batch_colors:
                self.batch_colors[b] = self.DEFAULT_BATCH_COLORS.get(b, "#E5E7EB")

        # NEW: batch labels (branch names etc.)
        self.batch_labels = batch_labels or {}

        # roll formatting
        self.roll_template = roll_template
        # map batch number -> prefix string (e.g. 1->'BTCS')
        self.batch_prefixes = batch_prefixes or {}
        # numeric year used in template if provided
        self.year = year
        # default start serial for batches
        self.start_serial = start_serial
        # per-batch start serial overrides
        self.start_serials = start_serials or {}
        # user-provided start roll strings per batch (e.g. {1: 'BTCS24O1135'})
        self.start_rolls = start_rolls or {}
        # NEW: per-batch real enrollment/roll strings
        self.batch_roll_numbers = batch_roll_numbers or {}
        # zero-pad width for serial portion
        self.serial_width = max(0, serial_width)
        # serial_mode: 'per_batch' or 'global'
        self.serial_mode = serial_mode

        self.seating_plan: List[List[Seat]] = []
        # Per-batch templates derived from start_rolls or batch_prefixes/year
        # batch_templates[b] is a string containing '{serial}' where the serial digits go
        self.batch_templates: Dict[int, str] = {}

        # populate batch_templates and per-batch start_serials from start_rolls if provided
        for b, s in list(self.start_rolls.items()):
            if not isinstance(s, str):
                continue
            s = s.strip()
            # find trailing digits (serial)
            import re

            m = re.search(r"(\d+)$", s)
            if m:
                serial_digits = m.group(1)
                prefix_part = s[: -len(serial_digits)]
                try:
                    serial_val = int(serial_digits)
                except ValueError:
                    continue
                # build template by replacing trailing digits with {serial}
                template = prefix_part + "{serial}"
                self.batch_templates[b] = template
                # set start serial and width inferred from provided string unless already set
                if b not in self.start_serials:
                    self.start_serials[b] = serial_val
                # if user didn't set serial_width explicitly, infer from length
                if (serial_width is None) or (serial_width == 0):
                    self.serial_width = max(self.serial_width, len(serial_digits))

    def generate_seating(self) -> List[List[Seat]]:
        """Generate seating arrangement with all constraints"""
        self.seating_plan = []

        # If using batch-by-column placement, construct roll pools per batch
        if self.batch_by_column:
            total = self.rows * self.cols
            # Count available seats (not broken)
            available_seats = total - len(self.broken_seats)

            # For column-major batch assignment, seats per batch should be based on how many
            # columns are assigned to each batch (not simply total // num_batches). Compute
            # columns distribution first, then multiply by rows to get seats per batch.
            base_cols = self.cols // self.num_batches
            rem_cols = self.cols % self.num_batches
            cols_per_batch = [
                base_cols + (1 if i < rem_cols else 0) for i in range(self.num_batches)
            ]
            batch_sizes = [cols_per_batch[i] * self.rows for i in range(self.num_batches)]

            # If batch_student_counts is provided, use those limits instead of batch_sizes
            # If batch_roll_numbers is provided, we prefer len(roll_numbers) as limit
            batch_limits: Dict[int, int] = {}
            for b in range(1, self.num_batches + 1):
                if self.batch_student_counts and b in self.batch_student_counts:
                    batch_limits[b] = self.batch_student_counts[b]
                elif self.batch_roll_numbers and b in self.batch_roll_numbers:
                    batch_limits[b] = len(self.batch_roll_numbers[b])
                else:
                    batch_limits[b] = batch_sizes[b - 1]

            # Track how many students have been allocated per batch
            batch_allocated = {b: 0 for b in range(1, self.num_batches + 1)}

            # Build roll queues
            from collections import deque

            batch_queues: Dict[int, deque] = {}
            next_roll = self.start_serial

            for i, size in enumerate(batch_sizes):
                b = i + 1

                # NEW: if real enrollment list is provided for this batch, use that directly
                if self.batch_roll_numbers and b in self.batch_roll_numbers:
                    # We don't pad or format; we just treat them as final roll/enrollment strings
                    rolls = [str(r).strip() for r in self.batch_roll_numbers[b] if str(r).strip()]
                    batch_queues[b] = deque(rolls)
                    continue

                # If no explicit template was provided but we have prefixes/year,
                # build a sensible default template e.g. 'BTCS24O{serial}'
                effective_template = self.roll_template
                if not effective_template and self.batch_prefixes and self.year is not None:
                    effective_template = "{prefix}{year}O{serial}"

                # Per-batch template preference: if user supplied a start-roll string for this batch,
                # it overrides the generic effective_template.
                batch_template = self.batch_templates.get(b, effective_template)

                # If roll_template/effective_template is not provided, keep numeric global numbering
                if not batch_template:
                    rolls = [str(next_roll + j) for j in range(size)]
                    batch_queues[b] = deque(rolls)
                    next_roll += size
                    continue

                # If serial_mode is 'per_batch', pre-generate per-batch formatted rolls
                if self.serial_mode == "per_batch":
                    s = self.start_serials.get(b, self.start_serial)
                    rolls = []
                    for j in range(size):
                        serial_val = s + j
                        prefix = self.batch_prefixes.get(b, "")
                        serial_str = (
                            str(serial_val).zfill(self.serial_width)
                            if self.serial_width
                            else str(serial_val)
                        )
                        # Try formatting with named fields; fall back to simple replacement if needed
                        try:
                            rolls.append(
                                batch_template.format(
                                    prefix=prefix, year=self.year or "", serial=serial_str
                                )
                            )
                        except Exception:
                            # If batch_template only contains '{serial}', do a replacement
                            rolls.append(batch_template.replace("{serial}", serial_str))
                    batch_queues[b] = deque(rolls)
                    next_roll += size
                    continue

                # serial_mode == 'global': we will assign serials on-the-fly during fill (use next_roll as global counter)
                # prepare an empty deque (we'll not use it)
                batch_queues[b] = deque()

            # Prepare seating grid
            for r in range(self.rows):
                self.seating_plan.append([None] * self.cols)

            # Fill seating column by column; each column assigned to a batch (col % num_batches)+1
            for col in range(self.cols):
                b = (col % self.num_batches) + 1
                for row in range(self.rows):
                    # Check if this seat is broken
                    if (row, col) in self.broken_seats:
                        seat = Seat(row=row, col=col, is_broken=True, color="#FF0000")  # Red for broken
                        self.seating_plan[row][col] = seat
                        continue

                    # If batch limit reached, mark as unallocated
                    if batch_allocated[b] >= batch_limits[b]:
                        seat = Seat(
                            row=row,
                            col=col,
                            batch=b,
                            paper_set=self._calculate_paper_set(row, col),
                            block=col // self.block_width,
                            roll_number=None,
                            color="#F3F4F6",
                        )
                        self.seating_plan[row][col] = seat
                        continue

                    # assign next roll from this batch if available
                    # if we are using real enrollments, they are already in batch_queues[b]
                    effective_template = self.roll_template
                    if (
                        not effective_template
                        and self.batch_prefixes
                        and self.year is not None
                    ):
                        effective_template = "{prefix}{year}O{serial}"

                    template_for_this_batch = self.batch_templates.get(b, effective_template)
                    rn = None

                    # If using real roll numbers, we just pop from the queue in the branch below
                    if (
                        template_for_this_batch
                        and self.serial_mode == "global"
                        and not (self.batch_roll_numbers and b in self.batch_roll_numbers)
                    ):
                        # generate formatted roll using global counter next_roll
                        serial_val = next_roll
                        next_roll += 1
                        prefix = self.batch_prefixes.get(b, "")
                        serial_str = (
                            str(serial_val).zfill(self.serial_width)
                            if self.serial_width
                            else str(serial_val)
                        )
                        try:
                            rn = template_for_this_batch.format(
                                prefix=prefix, year=self.year or "", serial=serial_str
                            )
                        except Exception:
                            rn = template_for_this_batch.replace("{serial}", serial_str)
                    elif batch_queues[b]:
                        # This covers both:
                        # - real enrollment numbers (batch_roll_numbers)
                        # - pre-generated serials
                        rn = batch_queues[b].popleft()

                    paper_set = self._calculate_paper_set(row, col)
                    block = col // self.block_width
                    if rn is not None:
                        batch_color = self.batch_colors.get(b, "#E5E7EB")
                        seat = Seat(
                            row=row,
                            col=col,
                            batch=b,
                            paper_set=paper_set,
                            block=block,
                            roll_number=str(rn),
                            color=batch_color,
                        )
                        self.seating_plan[row][col] = seat
                        batch_allocated[b] += 1
                    else:
                        # No more rolls available for this batch, mark as unallocated
                        seat = Seat(
                            row=row,
                            col=col,
                            batch=b,
                            paper_set=paper_set,
                            block=block,
                            roll_number=None,
                            color="#F3F4F6",
                        )
                        self.seating_plan[row][col] = seat
        else:
            # Alternative mode: simple row-wise assignment with sequential numbers
            roll = 1
            for row in range(self.rows):
                current_row: List[Seat] = []
                for col in range(self.cols):
                    # Check if this seat is broken
                    if (row, col) in self.broken_seats:
                        seat = Seat(row=row, col=col, is_broken=True, color="#FF0000")  # Red for broken
                        current_row.append(seat)
                        continue

                    # Calculate batch using row+column pattern to avoid vertical/horizontal collisions
                    batch = self._calculate_batch(row, col)

                    # Calculate paper set using row-based alternation
                    paper_set = self._calculate_paper_set(row, col)

                    # Calculate block
                    block = col // self.block_width

                    # Get batch color
                    batch_color = self.batch_colors.get(batch, "#E5E7EB")

                    seat = Seat(
                        row=row,
                        col=col,
                        batch=batch,
                        paper_set=paper_set,
                        block=block,
                        roll_number=str(roll),
                        color=batch_color,
                    )
                    current_row.append(seat)
                    roll += 1
                self.seating_plan.append(current_row)

        return self.seating_plan

    def _calculate_batch(self, row: int, col: int) -> int:
        """Calculate batch using both row and column so adjacent seats get different batches.

        This uses a simple offset pattern: (row + col) % num_batches + 1. It provides
        a good spread and avoids vertical/horizontal collisions for num_batches >= 2.
        """
        if self.num_batches <= 1:
            return 1
        return ((row + col) % self.num_batches) + 1

    def _calculate_paper_set(self, row: int, col: int) -> PaperSet:
        """Advanced paper-set calculation that respects priority constraints.

        Priority:
          1) Vertical alternation for same-batch seats (ensure different sets than the seat above if same batch)
          2) In-row same-batch alternation (if same batch already seated earlier in same block row, prefer opposite set)
          3) Horizontal alternation with immediate left neighbor if no higher-priority rule applied.

        This logic was taken from the routed implementation and preserves careful handling of block boundaries.
        """
        block = col // self.block_width
        start_col = block * self.block_width

        # Get current batch for this seat (consistent with column-major assignment)
        current_batch = (col % self.num_batches) + 1

        # Calculate base alternation: col_in_block and row determine the pattern
        col_in_block = col % self.block_width

        # Base pattern: alternates every column, and flips every row
        if row % 2 == 0:  # Even row
            base_set = PaperSet.A if col_in_block % 2 == 0 else PaperSet.B
        else:  # Odd row
            base_set = PaperSet.B if col_in_block % 2 == 0 else PaperSet.A

        # CONSTRAINT 3 (HIGH PRIORITY): Check vertically adjacent seat (same column, row-1)
        # This ensures same-batch vertical alternation
        if row > 0 and self.seating_plan and len(self.seating_plan) > row - 1:
            up = self.seating_plan[row - 1][col]
            if up and not up.is_broken and up.roll_number and up.batch == current_batch:
                # Same batch above! Alternate paper set
                base_set = PaperSet.B if up.paper_set == PaperSet.A else PaperSet.A
                return base_set

        # CONSTRAINT 2 (HIGH PRIORITY): Check if same batch already has students in this row/block
        # Only check BEFORE current column (already processed seats in this row)
        constraint2_triggered = False
        batch_papers_in_row = []
        for c in range(start_col, col):  # Only check before this column
            if self.seating_plan and len(self.seating_plan) > row:
                seat = self.seating_plan[row][c]
                if seat and seat.batch == current_batch and seat.roll_number:
                    batch_papers_in_row.append((c, seat.paper_set))

        # If same batch already has students in this row, ensure different paper set
        if len(batch_papers_in_row) > 0:
            used_sets = set(p for _, p in batch_papers_in_row)
            if len(used_sets) == 1:  # All same batch students have the same set
                first_set = list(used_sets)[0]
                # Switch to opposite - CONSTRAINT 2 TAKES PRIORITY
                base_set = PaperSet.B if first_set == PaperSet.A else PaperSet.A
                constraint2_triggered = True
            else:
                # Already have both sets used, choose the less frequent one
                count_a = sum(1 for _, s in batch_papers_in_row if s == PaperSet.A)
                count_b = len(batch_papers_in_row) - count_a
                if count_a > count_b:
                    base_set = PaperSet.B
                else:
                    base_set = PaperSet.A
                constraint2_triggered = True

        # CONSTRAINT 1: Check left neighbor for horizontal alternation
        # Only apply if CONSTRAINT 2 didn't need to override
        if not constraint2_triggered and col > start_col and self.seating_plan and len(self.seating_plan) > row:
            left = self.seating_plan[row][col - 1]
            if left and not left.is_broken and left.roll_number:
                # Ensure different from left neighbor
                if left.paper_set == base_set:
                    base_set = PaperSet.B if base_set == PaperSet.A else PaperSet.A

        return base_set

    # ------------------ validation helpers (unchanged) ------------------ #

    def validate_constraints(self) -> Tuple[bool, List[str]]:
        """Validate all seating constraints"""
        errors = []
        # Check 1: No same batch adjacent horizontally or vertically (optional, skip broken seats)
        if self.enforce_no_adjacent_batches:
            for r in range(self.rows):
                for c in range(self.cols):
                    seat = self.seating_plan[r][c]
                    if seat.is_broken:
                        continue
                    # right neighbor
                    if c + 1 < self.cols:
                        right = self.seating_plan[r][c + 1]
                        if not right.is_broken and seat.batch == right.batch:
                            errors.append(
                                f"Same batch adjacent horizontally at row {r}, cols {c}-{c+1}"
                            )
                    # bottom neighbor
                    if r + 1 < self.rows:
                        down = self.seating_plan[r + 1][c]
                        if not down.is_broken and seat.batch == down.batch:
                            errors.append(
                                f"Same batch adjacent vertically at col {c}, rows {r}-{r+1}"
                            )

        # Check 2: Paper sets alternate within each block (horizontally and vertically, skip broken)
        for block in range(self.blocks):
            start_col = block * self.block_width
            end_col = min(start_col + self.block_width, self.cols)
            for r in range(self.rows):
                for c in range(start_col, end_col):
                    seat = self.seating_plan[r][c]
                    if seat.is_broken:
                        continue
                    # horizontal within block
                    if c + 1 < end_col:
                        right = self.seating_plan[r][c + 1]
                        if not right.is_broken and seat.paper_set == right.paper_set:
                            errors.append(
                                f"Same paper set in block {block} horizontally at row {r}, cols {c}-{c+1}"
                            )
                    # vertical adjacent
                    if r + 1 < self.rows:
                        down = self.seating_plan[r + 1][c]
                        if not down.is_broken and seat.paper_set == down.paper_set:
                            errors.append(
                                f"Same paper set vertically at col {c}, rows {r}-{r+1}"
                            )

        # Check 3: No duplicate roll numbers and coverage (skip broken seats)
        seen_rolls = set()
        assigned_count = 0
        for r in range(self.rows):
            for c in range(self.cols):
                seat = self.seating_plan[r][c]
                if seat.is_broken or seat.roll_number is None:
                    continue
                rn = seat.roll_number
                if rn in seen_rolls:
                    errors.append(f"Duplicate roll number {rn} at row {r}, col {c}")
                seen_rolls.add(rn)
                assigned_count += 1
        # Expected total is number of non-broken, non-unallocated seats
        expected_total = assigned_count
        if len(seen_rolls) != expected_total:
            errors.append(
                f"Roll numbers count mismatch: expected {expected_total}, found {len(seen_rolls)}"
            )

        # Check 4: Blocks count matches expectation
        calculated_blocks = math.ceil(self.cols / self.block_width)
        if calculated_blocks != self.blocks:
            errors.append(
                f"Blocks mismatch: expected {self.blocks}, calculated {calculated_blocks}"
            )

        return len(errors) == 0, errors

    def get_constraints_status(self) -> Dict:
        """Get status of all applied constraints"""
        constraints = []

        # 1. Broken seats constraint
        constraints.append(
            {
                "name": "Broken Seats Handling",
                "description": f"Marks {len(self.broken_seats)} seats as unavailable",
                "applied": len(self.broken_seats) > 0,
                "satisfied": True
                if len(self.broken_seats) == 0
                else self._verify_broken_seats_respected(),
            }
        )

        # 2. Batch student counts constraint
        constraints.append(
            {
                "name": "Batch Student Counts",
                "description": f"Limits per-batch allocations: {dict(self.batch_student_counts) if self.batch_student_counts else 'Not set'}",
                "applied": bool(self.batch_student_counts),
                "satisfied": self._verify_batch_counts_respected(),
            }
        )

        # 3. Block width constraint
        constraints.append(
            {
                "name": "Block Width Enforcement",
                "description": f"Arranges {self.blocks} blocks of {self.block_width} columns each",
                "applied": True,
                "satisfied": self._verify_blocks_correct(),
            }
        )

        # 4. Paper set alternation constraint
        constraints.append(
            {
                "name": "Paper Set Alternation",
                "description": "Paper sets A and B alternate within blocks horizontally and vertically",
                "applied": True,
                "satisfied": self._verify_paper_sets_alternate(),
            }
        )

        # 5. Batch-by-column assignment
        constraints.append(
            {
                "name": "Batch-by-Column Assignment",
                "description": "Each column assigned to single batch, filled top-to-bottom",
                "applied": self.batch_by_column,
                "satisfied": self._verify_column_batch_assignment()
                if self.batch_by_column
                else True,
            }
        )

        # 6. No adjacent same batch constraint
        constraints.append(
            {
                "name": "No Adjacent Same Batch",
                "description": "Adjacent seats (horizontal/vertical) have different batches",
                "applied": self.enforce_no_adjacent_batches,
                "satisfied": self._verify_no_adjacent_batches()
                if self.enforce_no_adjacent_batches
                else True,
            }
        )

        # 7. Unallocated seats constraint
        unallocated_count = sum(
            1
            for row in self.seating_plan
            for seat in row
            if not seat.is_broken and seat.roll_number is None
        )
        constraints.append(
            {
                "name": "Unallocated Seats Handling",
                "description": f"Marks {unallocated_count} seats as unallocated (light gray)",
                "applied": unallocated_count > 0,
                "satisfied": True,
            }
        )

        return {
            "constraints": constraints,
            "total_satisfied": sum(1 for c in constraints if c["satisfied"]),
            "total_applied": sum(1 for c in constraints if c["applied"]),
        }

    def _verify_broken_seats_respected(self) -> bool:
        """Verify all broken seats are properly marked"""
        for row, col in self.broken_seats:
            if not self.seating_plan[row][col].is_broken:
                return False
        return True

    def _verify_batch_counts_respected(self) -> bool:
        """Verify batch student counts are respected"""
        if not self.batch_student_counts:
            return True
        allocated: Dict[int, int] = {}
        for row in self.seating_plan:
            for seat in row:
                if seat.roll_number and not seat.is_broken:
                    allocated[seat.batch] = allocated.get(seat.batch, 0) + 1
        for b, limit in self.batch_student_counts.items():
            if allocated.get(b, 0) > limit:
                return False
        return True

    def _verify_blocks_correct(self) -> bool:
        """Verify block structure is correct"""
        calculated = math.ceil(self.cols / self.block_width)
        return calculated == self.blocks

    def _verify_paper_sets_alternate(self) -> bool:
        """Verify paper sets alternate within blocks"""
        for block in range(self.blocks):
            start_col = block * self.block_width
            end_col = min(start_col + self.block_width, self.cols)
            for r in range(self.rows):
                for c in range(start_col, end_col):
                    seat = self.seating_plan[r][c]
                    if seat.is_broken or not seat.roll_number:
                        continue
                    if c + 1 < end_col:
                        right = self.seating_plan[r][c + 1]
                        if not right.is_broken and right.roll_number and seat.paper_set == right.paper_set:
                            return False
                    if r + 1 < self.rows:
                        down = self.seating_plan[r + 1][c]
                        if not down.is_broken and down.roll_number and seat.paper_set == down.paper_set:
                            return False
        return True

    def _verify_column_batch_assignment(self) -> bool:
        """Verify each column is assigned to single batch"""
        for col in range(self.cols):
            batches_in_col = set()
            for row in range(self.rows):
                seat = self.seating_plan[row][col]
                if not seat.is_broken and seat.roll_number:
                    batches_in_col.add(seat.batch)
            if len(batches_in_col) > 1:
                return False
        return True

    def _verify_no_adjacent_batches(self) -> bool:
        """Verify no adjacent seats have same batch"""
        for r in range(self.rows):
            for c in range(self.cols):
                seat = self.seating_plan[r][c]
                if seat.is_broken or not seat.roll_number:
                    continue
                if c + 1 < self.cols:
                    right = self.seating_plan[r][c + 1]
                    if not right.is_broken and right.roll_number and seat.batch == right.batch:
                        return False
                if r + 1 < self.rows:
                    down = self.seating_plan[r + 1][c]
                    if not down.is_broken and down.roll_number and seat.batch == down.batch:
                        return False
        return True

    # ------------------ web format ------------------ #

    def to_web_format(self) -> Dict:
        """Convert seating plan to web-friendly JSON format"""
        web_data = {
            "metadata": {
                "rows": self.rows,
                "cols": self.cols,
                "num_batches": self.num_batches,
                "blocks": self.blocks,
                "block_width": self.block_width,
            },
            "seating": [],
            "summary": self._generate_summary(),
        }

        for row_idx, row in enumerate(self.seating_plan):
            row_data = []
            for col_idx, seat in enumerate(row):
                # Human friendly batch label (branch name etc.)
                batch_label = self.batch_labels.get(seat.batch) if seat.batch else None

                # Handle broken seats
                if seat.is_broken:
                    seat_data = {
                        "position": f"{chr(65 + col_idx)}{row_idx + 1}",
                        "batch": None,
                        "batch_label": None,
                        "paper_set": None,
                        "block": None,
                        "roll_number": None,
                        "is_broken": True,
                        "display": "BROKEN",
                        "css_class": "seat-broken",
                        "color": "#FF0000",  # Red for broken
                    }
                else:
                    # Check if unallocated (no roll number assigned)
                    is_unallocated = seat.roll_number is None
                    set_val = seat.paper_set.value if seat.paper_set else ""
                    # This display string now effectively shows: enrollment + set
                    display_value = (
                        f"{seat.roll_number}{set_val}" if seat.roll_number else "UNALLOCATED"
                    )
                    css_class = (
                        f"batch-{seat.batch} set-{set_val}"
                        if seat.roll_number
                        else "seat-unallocated"
                    )
                    seat_data = {
                        "position": f"{chr(65 + col_idx)}{row_idx + 1}",
                        "batch": seat.batch,
                        # NEW: human readable branch/batch label
                        "batch_label": batch_label,
                        "paper_set": set_val or None,
                        "block": seat.block,
                        # This is now your enrollment number when batch_roll_numbers is used
                        "roll_number": seat.roll_number,
                        "is_broken": False,
                        "is_unallocated": is_unallocated,
                        "display": display_value,
                        "css_class": css_class,
                        "color": seat.color,
                    }
                row_data.append(seat_data)
            web_data["seating"].append(row_data)

        return web_data

    def _generate_summary(self) -> Dict:
        """Generate summary statistics including unallocated students"""
        batch_counts: Dict[int, int] = {}
        set_counts = {"A": 0, "B": 0}
        allocated_per_batch: Dict[int, int] = {}

        for row in self.seating_plan:
            for seat in row:
                if seat.is_broken or seat.roll_number is None:
                    continue
                batch_counts[seat.batch] = batch_counts.get(seat.batch, 0) + 1
                allocated_per_batch[seat.batch] = allocated_per_batch.get(seat.batch, 0) + 1
                if seat.paper_set:
                    set_counts[seat.paper_set.value] += 1

        # Calculate unallocated students per batch
        total_seats = self.rows * self.cols
        broken_seats_count = len(self.broken_seats)
        available_seats = total_seats - broken_seats_count

        # Calculate unallocated per batch
        unallocated_per_batch: Dict[int, int] = {}
        total_allocated = 0
        for b in range(1, self.num_batches + 1):
            allocated = allocated_per_batch.get(b, 0)
            total_allocated += allocated

            if self.batch_student_counts and b in self.batch_student_counts:
                # If batch_student_counts was provided, use those as expected limits
                expected = self.batch_student_counts[b]
            elif self.batch_roll_numbers and b in self.batch_roll_numbers:
                # Otherwise, if we know exact roll list, use its length
                expected = len(self.batch_roll_numbers[b])
            else:
                # Otherwise estimate based on column distribution
                base_per_batch = available_seats // self.num_batches
                rem_batches = available_seats % self.num_batches
                expected = base_per_batch + (1 if b - 1 < rem_batches else 0)

            unallocated = max(0, expected - allocated)
            unallocated_per_batch[b] = unallocated

        return {
            "batch_distribution": batch_counts,
            "paper_set_distribution": set_counts,
            "total_available_seats": available_seats,
            "total_allocated_students": total_allocated,
            "broken_seats_count": broken_seats_count,
            "unallocated_per_batch": unallocated_per_batch,
        }
