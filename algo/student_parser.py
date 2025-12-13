"""
student_parser.py

Robust Student Data Parser for seat-allocation pipeline.

Features:
- Accepts file path (str), bytes, or file-like (e.g., Flask UploadFile).
- Reads CSV or Excel (.csv, .xls, .xlsx) reliably, with magic-byte detection.
- Normalizes headers and auto-detects name & enrollment columns.
- Two extraction modes:
    mode=1 -> enrollment numbers only (list[str])
    mode=2 -> name + enrollment (list[dict])
- Returns a structured ParseResult with batch_id, counts, warnings, errors, and data.
"""

from __future__ import annotations

import io
import uuid
import re
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple, Union, Optional

import pandas as pd

logger = logging.getLogger("student_parser")
logger.setLevel(logging.INFO)


def _norm_col_name(x: Any) -> str:
    """Normalize column header: lowercase, no spaces/punct, alnum only."""
    if x is None:
        return ""
    s = str(x).strip().lower()
    s = re.sub(r"[^0-9a-z]", "", s)
    return s


def _normalize_enrollment_value(v: Any) -> str:
    """Normalize an enrollment value: strip, remove internal whitespace."""
    if v is None:
        return ""
    s = str(v).strip()
    s = re.sub(r"\s+", "", s)
    return s


@dataclass
class ParseResult:
    batch_id: str
    batch_name: str
    mode: int
    source_filename: Optional[str]
    rows_total: int
    rows_extracted: int
    warnings: List[Dict] = field(default_factory=list)
    errors: List[Dict] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)


class StudentDataParser:
    def __init__(
        self,
        enrollment_regex: str = r"^[A-Za-z0-9\-\_/]+$",
        supported_formats: Optional[List[str]] = None,
    ) -> None:
        self.enrollment_pattern = re.compile(enrollment_regex)
        self.supported_formats = supported_formats or [".csv", ".xlsx", ".xls"]
        self.last_parse_result: Optional[ParseResult] = None

    # ----------------------------------------------------------------------
    # File reading with CSV/XLSX detection
    # ----------------------------------------------------------------------
    def read_file(self, file_input: Union[str, bytes, io.BytesIO, Any]) -> pd.DataFrame:
        """
        Read a CSV/XLSX into a pandas DataFrame (dtype=str, keep_default_na=False).

        Supports:
        - Path string
        - bytes
        - file-like (has .read())
        """
        # Path string case
        if isinstance(file_input, str):
            p = Path(file_input)
            suffix = p.suffix.lower()
            if suffix not in self.supported_formats:
                raise ValueError(f"Unsupported file extension: {suffix}")

            if suffix == ".csv":
                # Try several encodings
                for enc in ("utf-8", "latin-1", "iso-8859-1"):
                    try:
                        return pd.read_csv(
                            file_input, dtype=str, keep_default_na=False, encoding=enc
                        )
                    except Exception:
                        continue
                raise ValueError("Failed to read CSV with common encodings")
            else:
                # Excel
                return pd.read_excel(file_input, dtype=str, keep_default_na=False)

        # Bytes case
        if isinstance(file_input, (bytes, bytearray)):
            head = bytes(file_input[:4]) if len(file_input) >= 4 else b""
            # XLSX = zip = PK\x03\x04
            if head.startswith(b"PK\x03\x04"):
                try:
                    return pd.read_excel(
                        io.BytesIO(file_input), dtype=str, keep_default_na=False
                    )
                except Exception as e:
                    raise ValueError("Failed to read XLSX from bytes: " + str(e))
            # Old XLS = D0 CF 11 E0 (compound file)
            if head.startswith(b"\xD0\xCF\x11\xE0"):
                try:
                    return pd.read_excel(
                        io.BytesIO(file_input), dtype=str, keep_default_na=False
                    )
                except Exception as e:
                    raise ValueError("Failed to read XLS from bytes: " + str(e))
            # Fallback: treat as CSV
            for enc in ("utf-8", "latin-1"):
                try:
                    text = file_input.decode(enc)
                    return pd.read_csv(
                        io.StringIO(text), dtype=str, keep_default_na=False
                    )
                except Exception:
                    continue
            raise ValueError("Unable to parse bytes as CSV or Excel")

        # File-like (e.g., Flask FileStorage, UploadFile.stream)
        if hasattr(file_input, "read"):
            # peek a bit for magic bytes
            try:
                pos = file_input.tell()
            except Exception:
                pos = None

            head = file_input.read(8)
            try:
                if pos is not None:
                    file_input.seek(pos)
                else:
                    file_input.seek(0)
            except Exception:
                pass

            # head as bytes?
            if isinstance(head, (bytes, bytearray)):
                if head.startswith(b"PK\x03\x04") or head.startswith(
                    b"\xD0\xCF\x11\xE0"
                ):
                    # Excel
                    try:
                        content = file_input.read()
                        if not isinstance(content, (bytes, bytearray)):
                            content = str(content).encode("utf-8")
                        return pd.read_excel(
                            io.BytesIO(content), dtype=str, keep_default_na=False
                        )
                    except Exception as e:
                        try:
                            file_input.seek(0)
                        except Exception:
                            pass
                        raise ValueError("Failed to read Excel upload: " + str(e))

                # Not clearly Excel; try CSV
                content = file_input.read()
                try:
                    file_input.seek(0)
                except Exception:
                    pass
                if isinstance(content, (bytes, bytearray)):
                    for enc in ("utf-8", "latin-1"):
                        try:
                            text = content.decode(enc)
                            return pd.read_csv(
                                io.StringIO(text),
                                dtype=str,
                                keep_default_na=False,
                            )
                        except Exception:
                            continue
                else:
                    return pd.read_csv(
                        io.StringIO(str(content)), dtype=str, keep_default_na=False
                    )

                # fallback excel
                try:
                    file_input.seek(0)
                except Exception:
                    pass
                return pd.read_excel(file_input, dtype=str, keep_default_na=False)

            # head is text
            content = file_input.read()
            try:
                file_input.seek(0)
            except Exception:
                pass
            return pd.read_csv(
                io.StringIO(str(head) + str(content)),
                dtype=str,
                keep_default_na=False,
            )

        raise ValueError("Unsupported input type for read_file")

    # ----------------------------------------------------------------------
    # Column detection
    # ----------------------------------------------------------------------
    def detect_columns(self, df: pd.DataFrame) -> Dict[str, Optional[str]]:
        """
        Auto-detect likely 'name' and 'enrollment' columns.
        Returns: {'name': original_col_or_None, 'enrollment': original_col_or_None}
        """
        detected = {"name": None, "enrollment": None}
        norm_map: Dict[str, str] = {}
        for c in df.columns:
            norm_map[_norm_col_name(c)] = c

        enroll_keys = [
            "enrollment",
            "enrollmentno",
            "enroll",
            "enrollno",
            "enrollmentnumber",
            "roll",
            "rollno",
            "regno",
            "registrationno",
            "studentid",
            "id",
            "matricno",
        ]
        name_keys = ["name", "studentname", "fullname", "candidate", "firstname", "fname"]

        # exact normalized key
        for key in enroll_keys:
            if key in norm_map:
                detected["enrollment"] = norm_map[key]
                break
        for key in name_keys:
            if key in norm_map:
                detected["name"] = norm_map[key]
                break

        # fallback: substring
        if detected["enrollment"] is None:
            for norm, orig in norm_map.items():
                if any(k in norm for k in enroll_keys):
                    detected["enrollment"] = orig
                    break

        if detected["name"] is None:
            for norm, orig in norm_map.items():
                if any(k in norm for k in name_keys):
                    detected["name"] = orig
                    break

        return detected

    # ----------------------------------------------------------------------
    # Extraction
    # ----------------------------------------------------------------------
    def extract_mode1(
        self, df: pd.DataFrame, enrollment_col: Optional[str] = None
    ) -> Tuple[List[str], List[Dict]]:
        """
        Mode 1: extract only enrollment numbers.
        Returns (enrollments_list, warnings_list)
        """
        warnings: List[Dict] = []
        detected = self.detect_columns(df)
        if enrollment_col is None:
            enrollment_col = detected.get("enrollment")

        if enrollment_col is None or enrollment_col not in df.columns:
            raise ValueError(
                f"Enrollment column not found. Available columns: {df.columns.tolist()}"
            )

        enrollments: List[str] = []
        for idx, value in enumerate(df[enrollment_col].tolist(), start=1):
            if value is None or value == "" or (isinstance(value, float) and pd.isna(value)):
                warnings.append({"row": idx, "issue": "empty_enrollment", "value": None})
                continue
            norm = _normalize_enrollment_value(value)
            if not self.enrollment_pattern.match(norm):
                warnings.append(
                    {
                        "row": idx,
                        "issue": "invalid_enrollment_format",
                        "value": value,
                    }
                )
                # still include normalized
            enrollments.append(norm)
        return enrollments, warnings

    def extract_mode2(
        self,
        df: pd.DataFrame,
        name_col: Optional[str] = None,
        enrollment_col: Optional[str] = None,
    ) -> Tuple[List[Dict[str, str]], List[Dict]]:
        """
        Mode 2: extract name + enrollment.
        Returns (students_list, warnings_list)
        students_list entry: {'name': ..., 'enrollmentNo': ...}
        """
        warnings: List[Dict] = []
        detected = self.detect_columns(df)
        if enrollment_col is None:
            enrollment_col = detected.get("enrollment")
        if name_col is None:
            name_col = detected.get("name")

        if enrollment_col is None or enrollment_col not in df.columns:
            raise ValueError(
                f"Enrollment column not found. Available columns: {df.columns.tolist()}"
            )
        if name_col is None or name_col not in df.columns:
            warnings.append(
                {
                    "issue": "name_column_not_found",
                    "available_columns": df.columns.tolist(),
                }
            )
            name_col = None

        students: List[Dict[str, str]] = []
        for idx, row in enumerate(df.to_dict(orient="records"), start=1):
            raw_en = row.get(enrollment_col)
            if raw_en is None or raw_en == "":
                warnings.append({"row": idx, "issue": "empty_enrollment", "value": None})
                continue
            enroll_norm = _normalize_enrollment_value(raw_en)
            if not self.enrollment_pattern.match(enroll_norm):
                warnings.append(
                    {
                        "row": idx,
                        "issue": "invalid_enrollment_format",
                        "value": raw_en,
                    }
                )
            name_val = ""
            if name_col:
                nv = row.get(name_col)
                name_val = "" if nv is None else str(nv).strip()
            students.append({"name": name_val, "enrollmentNo": enroll_norm})
        return students, warnings

    # ----------------------------------------------------------------------
    # Public parse API
    # ----------------------------------------------------------------------
    def parse_file(
        self,
        file_input: Union[str, bytes, io.BytesIO, Any],
        mode: int = 2,
        batch_name: str = "BATCH1",
        name_col: Optional[str] = None,
        enrollment_col: Optional[str] = None,
    ) -> ParseResult:
        """
        Main parse entrypoint.
        Returns a ParseResult with data formatted as:
            mode=1 -> {"BATCH1": ["E1","E2",...]}
            mode=2 -> {"BATCH1": [{"name":..,"enrollmentNo":..}, ...]}
        """
        df = self.read_file(file_input)
        source_filename = None
        if isinstance(file_input, str):
            source_filename = Path(file_input).name
        elif hasattr(file_input, "filename"):
            source_filename = getattr(file_input, "filename")

        rows_total = len(df)
        warnings: List[Dict] = []

        if mode == 1:
            extracted, warnings = self.extract_mode1(df, enrollment_col)
            formatted = {batch_name: extracted}
        elif mode == 2:
            extracted, warnings = self.extract_mode2(df, name_col, enrollment_col)
            formatted = {batch_name: extracted}
        else:
            raise ValueError("mode must be 1 or 2")

        pr = ParseResult(
            batch_id=str(uuid.uuid4()),
            batch_name=batch_name,
            mode=mode,
            source_filename=source_filename,
            rows_total=rows_total,
            rows_extracted=len(formatted[batch_name]),
            warnings=warnings,
            errors=[],
            data=formatted,
        )
        self.last_parse_result = pr
        return pr

    # ----------------------------------------------------------------------
    # Preview
    # ----------------------------------------------------------------------
    def preview(
        self, file_input: Union[str, bytes, io.BytesIO, Any], max_rows: int = 5
    ) -> Dict[str, Any]:
        df = self.read_file(file_input)
        detected = self.detect_columns(df)
        sample = df.head(max_rows).fillna("").to_dict(orient="records")
        return {
            "columns": list(map(str, df.columns.tolist())),
            "detectedColumns": detected,
            "sampleData": sample,
            "totalRows": len(df),
        }

    # ----------------------------------------------------------------------
    # JSON helpers
    # ----------------------------------------------------------------------
    def to_json_str(self, parse_result: Optional[ParseResult] = None) -> str:
        if parse_result is None:
            parse_result = self.last_parse_result
        if parse_result is None:
            raise ValueError("No parse result available")
        return json.dumps(
            {
                "batch_id": parse_result.batch_id,
                "batch_name": parse_result.batch_name,
                "mode": parse_result.mode,
                "source": parse_result.source_filename,
                "rows_total": parse_result.rows_total,
                "rows_extracted": parse_result.rows_extracted,
                "warnings": parse_result.warnings,
                "errors": parse_result.errors,
                "data": parse_result.data,
            },
            ensure_ascii=False,
            indent=2,
        )

    def to_json_file(self, path: str, parse_result: Optional[ParseResult] = None) -> None:
        s = self.to_json_str(parse_result)
        Path(path).write_text(s, encoding="utf-8")
