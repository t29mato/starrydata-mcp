"""Best-effort parsing of Starrydata's free-form `composition` field into a
tuple of constituent element symbols.

Design note (docs/design/architecture.md §1.2, §5 Q3): the real dataset's
`composition` column is *mostly* clean chemical formulas (e.g. "Bi2Te3") but
sometimes free-text notes (e.g. "PH1000 with DMSO ... doping agent"). A
mis-parse that silently returns wrong elements is worse than an honest empty
result, so this parser is strict: it only accepts strings that are *entirely*
composed of `<ElementSymbol><optional decimal stoichiometry>` tokens back to
back, with nothing left over. Anything else — including composite/mixture
notations with separators like " - " — returns an empty tuple, and callers
are expected to fall back to substring search on the raw composition text.

A full normalizer (e.g. via `pymatgen.core.Composition`) is deliberately out
of scope for v1; see the design doc for the rationale.
"""

from __future__ import annotations

import re

# The 118 IUPAC element symbols (as of element 118, Oganesson).
ELEMENT_SYMBOLS: frozenset[str] = frozenset(
    """
    H He Li Be B C N O F Ne Na Mg Al Si P S Cl Ar K Ca Sc Ti V Cr Mn Fe Co Ni
    Cu Zn Ga Ge As Se Br Kr Rb Sr Y Zr Nb Mo Tc Ru Rh Pd Ag Cd In Sn Sb Te I
    Xe Cs Ba La Ce Pr Nd Pm Sm Eu Gd Tb Dy Ho Er Tm Yb Lu Hf Ta W Re Os Ir Pt
    Au Hg Tl Pb Bi Po At Rn Fr Ra Ac Th Pa U Np Pu Am Cm Bk Cf Es Fm Md No Lr
    Rf Db Sg Bh Hs Mt Ds Rg Cn Nh Fl Mc Lv Ts Og
    """.split()
)

_TOKEN = re.compile(r"([A-Z][a-z]?)(\d*\.?\d*)")


def parse_elements(composition_raw: str | None) -> tuple[str, ...]:
    """Return the distinct element symbols in `composition_raw`, in first-seen
    order, or `()` if the string doesn't parse cleanly as a single formula.

    Never raises.
    """
    if not composition_raw:
        return ()
    text = composition_raw.strip()
    if not text:
        return ()

    symbols: list[str] = []
    pos = 0
    while pos < len(text):
        match = _TOKEN.match(text, pos)
        if match is None or not match.group(1) or match.end() == pos:
            return ()
        symbol = match.group(1)
        if symbol not in ELEMENT_SYMBOLS:
            return ()
        symbols.append(symbol)
        pos = match.end()

    seen: set[str] = set()
    ordered: list[str] = []
    for symbol in symbols:
        if symbol not in seen:
            seen.add(symbol)
            ordered.append(symbol)
    return tuple(ordered)
