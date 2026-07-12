"""HL7 message parser for health interoperability."""

import re
from dataclasses import dataclass, field


@dataclass
class HL7Segment:
  name: str
  fields: list[str] = field(default_factory=list)


@dataclass
class HL7Message:
  segments: list[HL7Segment] = field(default_factory=list)
  message_type: str = ""
  patient_id: str = ""


class HL7Parser:
  """Parse HL7 v2.x messages into structured data."""

  FIELD_SEPARATOR = "|"
  COMPONENT_SEPARATOR = "^"

  def parse(self, raw_message: str) -> HL7Message:
    lines = [line.strip() for line in raw_message.strip().split("\n") if line.strip()]
    segments = []

    for line in lines:
      fields = line.split(self.FIELD_SEPARATOR)
      segment = HL7Segment(name=fields[0], fields=fields[1:])
      segments.append(segment)

    message = HL7Message(segments=segments)
    message.message_type = self._extract_message_type(segments)
    message.patient_id = self._extract_patient_id(segments)
    return message

  def _extract_message_type(self, segments: list[HL7Segment]) -> str:
    for seg in segments:
      if seg.name == "MSH" and len(seg.fields) >= 8:
        return seg.fields[7]
    return ""

  def _extract_patient_id(self, segments: list[HL7Segment]) -> str:
    for seg in segments:
      if seg.name == "PID" and seg.fields:
        return seg.fields[2].split(self.COMPONENT_SEPARATOR)[0]
    return ""

  def validate(self, raw_message: str) -> bool:
    if not raw_message.strip():
      return False
    first_line = raw_message.strip().split("\n")[0]
    return bool(re.match(r"^MSH\|", first_line))
