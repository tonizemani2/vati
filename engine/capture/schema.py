"""Capture artifacts — the brief, the target, the play, the tree, the rating.

Plain dataclasses + dict round-trips so a play is a reviewable JSON file on disk
(data/capture/<slug>/). No DB table yet: a play is small, human-reviewed, and immutable
once approved — a file is the honest store.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path


# --- the seed: what we're trying to capture -------------------------------------------

@dataclass
class PlayBrief:
    """A capture campaign. Reusable for ANY criteria — v1 ships a critical-minerals
    data-barter brief, but discovery_queries + value_hook + linked_forecast are all
    free-text so the same engine runs a Ring-1-advisor or lighthouse-client play."""
    slug: str
    objective: str            # the capture goal, in one line
    rung: int                 # capture ladder rung this play lives at (1-2 = pre-capital)
    target_criteria: str      # who we are looking for, in plain words
    discovery_queries: list[str]
    linked_forecast: str      # the live call the hook rides on (the reason-to-contact)
    value_hook: str           # what we GIVE before we take

    def to_dict(self) -> dict:
        return asdict(self)


# --- a discovered + qualified target --------------------------------------------------

@dataclass
class Target:
    name: str
    org: str
    role: str = ""
    url: str = ""
    why_them: str = ""           # one line: why this node sits at the bottleneck
    what_they_have: str = ""     # the proprietary data/access we want (the barter)
    reachability: str = ""       # email / handle / public path, or "unknown"
    # qualify scores (0-10), filled by DeepSeek then sanity-checked by the rater
    fit: int = 0
    leverage: int = 0            # door + credibility + capital, not just one
    warm_path: int = 0           # 10 = warm/second-degree, 0 = cold
    reach_ease: int = 0
    score: float = 0.0           # blended rank key

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Target":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


# --- the play: opener + the tree ------------------------------------------------------

@dataclass
class TreeNode:
    """One branch of the conversation. reply_type = the kind of answer we anticipate;
    our_move = what we send back; children = the next level of likely replies."""
    reply_type: str
    our_move: str
    children: list["TreeNode"] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"reply_type": self.reply_type, "our_move": self.our_move,
                "children": [c.to_dict() for c in self.children]}

    @classmethod
    def from_dict(cls, d: dict) -> "TreeNode":
        return cls(reply_type=d.get("reply_type", ""), our_move=d.get("our_move", ""),
                   children=[cls.from_dict(c) for c in d.get("children", [])])


@dataclass
class Play:
    target: Target
    rung: int
    hook: str                    # the specific valuable thing, tied to the forecast
    opener: str                  # the first message (Toni voice, no em dash, evidence-first)
    channel: str                 # "email" | "x" | "linkedin-out" etc.
    tree: list[TreeNode] = field(default_factory=list)
    rating: dict | None = None   # the Opus verdict, attached after review

    def to_dict(self) -> dict:
        return {"target": self.target.to_dict(), "rung": self.rung, "hook": self.hook,
                "opener": self.opener, "channel": self.channel,
                "tree": [n.to_dict() for n in self.tree], "rating": self.rating}

    @classmethod
    def from_dict(cls, d: dict) -> "Play":
        return cls(target=Target.from_dict(d["target"]), rung=d.get("rung", 1),
                   hook=d.get("hook", ""), opener=d.get("opener", ""),
                   channel=d.get("channel", "email"),
                   tree=[TreeNode.from_dict(n) for n in d.get("tree", [])],
                   rating=d.get("rating"))


# --- on-disk store --------------------------------------------------------------------

def play_dir(slug: str, repo_root: Path) -> Path:
    d = repo_root / "data" / "capture" / slug
    d.mkdir(parents=True, exist_ok=True)
    return d


def write_json(path: Path, obj) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False))


def read_json(path: Path):
    return json.loads(path.read_text())
