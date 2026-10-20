from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass

from anypatch.formats.xdelta_vectors_test_support import edited, moved, noise, text

ESCAPE_HEAVY = b"\xa2\xa3\xa4\xa5\xa6\xa7xy"


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    source: bytes
    target: bytes


def escapes(size: int, seed: int) -> bytes:
    return bytes(ESCAPE_HEAVY[value % len(ESCAPE_HEAVY)] for value in noise(size, seed))


def cases() -> list[Case]:
    small, wide, codes = text(8000, 61), text(70000, 63), escapes(6000, 65)
    return [
        Case("edit", small, edited(small, 71, 12)),
        Case("grow", small, small + text(3000, 72)),
        Case("shrink", small, small[:5000]),
        Case("moved", wide, moved(wide, 73)),
        Case("escapes", codes, edited(codes, 74, 40) + escapes(500, 75)),
    ]


def _decoded(chunks: tuple[str, ...]) -> bytes:
    return base64.b64decode("".join(chunks))


PATCHES: Mapping[str, bytes] = {
    "edit": _decoded(
        (
            "p6NiMgnRZm8ep6P9BkhS3FxFSdCno/0CgMaXYTgGF6ej/QWPjDreP6j0p6Mr3yFYUoyJp6P9BGyF8Up5U7Ono/0C/2xn",
            "U1/OQaej+visT2wR+qej/Gr/9OMyZTuno/0CBr9OzHOy1qej/QKSpcTVWS1lp6O1GX/aTOqsp6P2",
        )
    ),
    "grow": _decoded(
        (
            "p6P9H0CnpXJvbSB6ZWxkYSBmbGFzaCBtYXNrIHJvbSB6ZWxkYSB3aW5kb3cgc2xvdCBhZGQgdGFibGUgc2xvdCBzcmFt",
            "IHBhdGNoIHNhdmUgcGFnZSBtYXNrIHBhdGNoIGFkZCBtYXNrIGFkZCB6ZWxkYSBtYXNrIHRhYmxlIHdpbmRvdyBydW4g",
            "YWRkIGR1bXAgdGFibGUgc25hcCBhZGQgcnVuIGZsYXNoIG1hc2sgc25hcCBwYWdlIHBhdGNoIGFkZCBzYXZlIG1hc2sg",
            "cnVuIHNyYW0gc2F2ZSBwYXRjaCBzcmFtIGZsYXNoIHNyYW0gc2xvdCBhZGQgc2xvdCBzcmFtIHNyYW0gc2xvdCBzbG90",
            "IGR1bXAgcGFnZSBzYXZlIHNhdmUgcm9tIHJvbSBwYXRjaCBwYXRjaCB6ZWxkYSBmbGFzaCBwYWdlIHJvbSBwYWdlIHNy",
            "YW0gZHVtcCBzYXZlIHBhZ2UgemVsZGEgZmxhc2ggcnVuIGR1bXAgcGF0Y2ggcGFnZSBhZGQgcm9tIHJvbSBmbGFzaCBz",
            "bG90IHNuYXAgc2xvdCBmbGFzaCBtYXNrIHNsb3QgZmxhc2ggcm9tIHplbGRhIG1hc2sgc25hcCBhZGQgZmxhc2ggd2lu",
            "ZG93IHNyYW0gY29weSByb20gYWRkIHRhYmxlIGNvcHkgc2xvdCBzbmFwIGZsYXNoIHNyYW0gY29weSBkdW1wIGFkZCBh",
            "ZGQgZHVtcCBwYWdlIHNyYW0gc25hcCBwYWdlIHdpbmRvdyByb20gcnVuIGR1bXAgY29weSByb20gemVsZGEgZHVtcCB3",
            "aW5kb3cgZHVtcCB6ZWxkYSBzcmFtIHplbGRhIHplbGRhIHNuYXAgZmxhc2ggc2F2ZSB0YWJsZSBwYXRjaCBmbGFzaCBw",
            "YXRjaCBydW4gc25hcCBzbG90IHNuYXAgd2luZG93IHBhdGNoIHJ1biBzcmFtIHNhdmUgYWRkIHNuYXAgc2xvdCBmbGFz",
            "aCBzbG90IGZsYXNoIGFkZCBkdW1wIHBhdGNoIHNyYW0gcGF0Y2ggc3JhbSBjb3B5IG1hc2sgcnVuIGR1bXAgY29weSBz",
            "YXZlIHBhZ2Ugc25hcCB3aW5kb3cgZmxhc2ggc2F2ZSBtYXNrIHJ1biB3aW5kb3cgY29weSB3aW5kb3cgZmxhc2ggc2xv",
            "dCBzbmFwIHJvbSB6ZWxkYSBjb3B5IG1hc2sgY29weSBtYXNrIHplbGRhIGNvcHkgcm9tIHNuYXAgemVsZGEgcGF0Y2gg",
            "bWFzayBkdW1wIGR1bXAgd2luZG93IHBhZ2UgZmxhc2ggc25hcCBhZGQgZHVtcCBkdW1wIGR1bXAgc2F2ZSBzbG90IHBh",
            "dGNoIHdpbmRvdyBzYXZlIHplbGRhIHNuYXAgZmxhc2ggc3JhbSBydW4gY29weSBzbmFwIHNhdmUgc2F2ZSBzbG90IHNy",
            "YW0gc2xvdCBmbGFzaCBkdW1wIHNyYW0gcm9tIHRhYmxlIHNsb3Qgc2F2ZSByb20gc25hcCBydW4gdGFibGUgc25hcCBy",
            "dW4gcGF0Y2ggcm9tIHNsb3Qgd2luZG93IHplbGRhIGFkZCBzbmFwIHBhZ2UgcGF0Y2ggYWRkIHNsb3Qgc2F2ZSBtYXNr",
            "IHNsb3Qgc2xvdCB0YWJsZSBzYXZlIHdpbmRvdyBkdW1wIHNsb3QgdGFibGUgc25hcCBwYWdlIHNhdmUgcGFnZSBmbGFz",
            "aCByb20gc2xvdCBjb3B5IHdpbmRvdyB3aW5kb3cgc2F2ZSBtYXNrIHBhdGNoIHNyYW0gbWFzayBzbmFwIHNuYXAgc2F2",
            "ZSBwYXRjaCBydW4gc3JhbSB6ZWxkYSBwYWdlIHNhdmUgdGFibGUgd2luZG93IGZsYXNoIHNsb3QgcGF0Y2ggemVsZGEg",
            "cm9tIHNsb3QgdGFibGUgZHVtcCBzcmFtIGZsYXNoIHplbGRhIHNyYW0gY29weSBzbG90IHJvbSBzYXZlIHJvbSBtYXNr",
            "IHNyYW0gc2xvdCBydW4gc25hcCBzbG90IGNvcHkgdGFibGUgd2luZG93IHplbGRhIHBhZ2Ugc2F2ZSB3aW5kb3cgcm9t",
            "IGZsYXNoIGFkZCBtYXNrIG1hc2sgcGFnZSBzYXZlIGNvcHkgYWRkIHNsb3Qgc3JhbSBzbG90IG1hc2sgc2xvdCBwYXRj",
            "aCBwYXRjaCBwYXRjaCBwYXRjaCBzbmFwIHRhYmxlIHNsb3QgZmxhc2ggc25hcCBmbGFzaCBzbmFwIHNuYXAgc25hcCBw",
            "YXRjaCBwYWdlIHNhdmUgYWRkIHRhYmxlIGNvcHkgZHVtcCBzbG90IHBhZ2Ugd2luZG93IHplbGRhIHNuYXAgc25hcCB3",
            "aW5kb3cgemVsZGEgbWFzayBzbG90IGFkZCBwYWdlIHplbGRhIHBhdGNoIHBhZ2UgemVsZGEgc2F2ZSB0YWJsZSB6ZWxk",
            "YSBmbGFzaCBydW4gemVsZGEgYWRkIGR1bXAgcnVuIHBhZ2Ugc2F2ZSB6ZWxkYSB0YWJsZSBzcmFtIHBhZ2UgcnVuIGR1",
            "bXAgY29weSBjb3B5IHNuYXAgZHVtcCBydW4gcm9tIGNvcHkgY29weSBwYXRjaCBydW4gemVsZGEgbWFzayB3aW5kb3cg",
            "cm9tIHBhdGNoIHBhZ2Ugc2F2ZSBzbG90IHdpbmRvdyBtYXNrIHNsb3Qgd2luZG93IGR1bXAgZmxhc2ggYWRkIHNsb3Qg",
            "cnVuIGFkZCB3aW5kb3cgZmxhc2ggbWFzayBzbmFwIHNhdmUgc2xvdCBwYWdlIGR1bXAgbWFzayByb20gY29weSBzbmFw",
            "IHJ1biB0YWJsZSBzbmFwIHplbGRhIHRhYmxlIHdpbmRvdyBydW4gZHVtcCBydW4gcGFnZSBkdW1wIGNvcHkgcnVuIHBh",
            "dGNoIHNhdmUgc2xvdCBzcmFtIG1hc2sgc2F2ZSBzYXZlIHBhdGNoIGNvcHkgY29weSB6ZWxkYSBzcmFtIHNuYXAgd2lu",
            "ZG93IGZsYXNoIHdpbmRvdyBwYWdlIHJ1biBzcmFtIHNuYXAgcm9tIHJ1biBwYXRjaCBzYXZlIHdpbmRvdyB3aW5kb3cg",
            "cnVuIGR1bXAgd2luZG93IHNsb3QgdGFibGUgZmxhc2ggc2xvdCBzbG90IHNyYW0gemVsZGEgdGFibGUgc3JhbSBzbG90",
            "IHplbGRhIHNhdmUgcm9tIHJ1biB3aW5kb3cgc2xvdCBjb3B5IG1hc2sgc3JhbSB0YWJsZSBwYXRjaCBzcmFtIHNhdmUg",
            "cGF0Y2ggcGFnZSB3aW5kb3cgcGFnZSBzYXZlIG1hc2sgemVsZGEgc25hcCB6ZWxkYSBmbGFzaCBtYXNrIHNyYW0gY29w",
            "eSBydW4gc3JhbSB6ZWxkYSBmbGFzaCBjb3B5IGZsYXNoIHplbGRhIHNyYW0gd2luZG93IHplbGRhIHRhYmxlIGNvcHkg",
            "d2luZG93IHJvbSBwYWdlIHBhZ2UgZHVtcCBmbGFzaCBjb3B5IHdpbmRvdyB3aW5kb3cgcGFnZSByb20gYWRkIGNvcHkg",
            "d2luZG93IHBhZ2Ugd2luZG93IHNuYXAgcnVuIHNuYXAgcnVuIHplbGRhIGNvcHkgbWFzayB0YWJsZSBkdW1wIHNhdmUg",
            "c2xvdCBwYXRjaCByb20gemVsZGEgcm9tIHdpbmRvdyBwYWdlIHNsb3QgemVsZGEgemVsZGEgcGFnZSByb20gbWFzayBm",
            "bGFzaCBzcmFtIHplbGRhIHNyYW0gc2F2ZSBzcmFtIHJvbSBmbGFzaCBwYWdlIHNsb3Qgc3JhbSBzYXZlIHNyYW0gcm9t",
            "IHBhdGNoIHNyYW0gc25hcCBzYXZlIG1hc2sgdGFibGUgcGFnZSB3aW5kb3cgemVsZGEgemVsZGEgbWFzayBtYXNrIHNu",
            "YXAgcm9tIHplbGRhIGNvcHkgZHVtcCBzbmFwIHNyYW0gY29weSBmbA==",
        )
    ),
    "shrink": _decoded(("p6P9E4g=",)),
    "moved": _decoded(
        (
            "p6T9WyWno/0D8/isT2wR+qej/QXMbxeNKVbwp6P9BQyee0GT2CSno/0EDPxdiDaYqaej/RRIPQOf9UwNp6P8+rcGOK1d",
            "lqej/QkOpcTVWS1lp6P9CVAcMBQVcluno/0KkTW6Cy/3zKej/Qs13yFYUoyJp6P9CWDi0pIcEzeno/0L2zIJ0WZvHqej",
            "/QaGETZGhpZrp6P8o5czrc6E46ej/QUGREszuqBOp6P9BNrqGybhaHino/0PnGxnU1/OQaej/QL9kOoYCC+ip6P9AgMr",
            "wT2gG92no/0C5laNlg/Rf6ej/QRJdmAh7qoxp6ODZB6/mnoBp6P9FuC/TsxzstanozCpdQ8itRSno/0E2YXxSnlTs6ej",
            "/Mh+qLa0/3Kno/0DNqei/gABEXCno/0ZhslImwKOxqej/Q0KS5TIgPWPp6P9BbZd1SrUJcCno47C/wY8OoWno/xyGX/a",
            "TOqsp6P8ltjZw403SKej/MpS3FxFSdCno/0CjvFjuqe8uaej/QZIA6Ud++3qp6P9BXSwvaToCVWnowMK7rHBQSuno/0H",
            "8CN4qNvGnKej/QR+0JAvx+MHp6P86Yw63j+o9Kej/QyRp6L9WyWnpW1hc2sgd2luZG93IHJ1biB3aW5kb3cgZmxhc2gg",
            "ZHVtcCB6ZWxkYSBwYWdlIHJ1biBtYXNrIHNsb3QgcGF0Y2ggcnVuIHNyYW0gcGFnZSB3aW5kb3cgdGFibGUgcGFnZSBy",
            "dW4gdGFibGUgc25hcCBhZGQgZHVtcCBzYXZlIHNyYW0gcGF0Y2ggcnVuIHJvbSBzbG90IHNyYW0gcGF0Y2ggZmxhc2gg",
            "c25hcCBzbmFwIHRhYmxlIHJvbSBzYXZlIGFkZCBmbGFzaCBydW4gemVsZGEgcGFnZSBzbmFwIGR1bXAgZHVtcCB3aW5k",
            "b3cgcm9tIHNsb3Qgc25hcCBkdW1wIGZsYXNoIHBhZ2UgcGF0Y2ggdGFibGUgd2luZG93IHRhYmxlIHRhYmxlIHBhdGNo",
            "IHJ1biB3aW5kb3cgbWFzayBwYXRjaCBzbG90IHJvbSBhZGQgZmxhc2ggc3JhbSBhZGQgc3JhbSBydW4gZHVtcCBzbG90",
            "IHNyYW0gcnVuIHNyYW0gY29weSByb20gZHVtcCBzbG90IHBhdGNoIGFkZCBtYXNrIHJvbSBkdW1wIGNvcHkgcm9tIG1h",
            "c2sgc2F2ZSB6ZWxkYSBtYXNrIHNhdmUgZmxhc2ggcGF0Y2ggc2xvdCB0YWJsZSB0YWJsZSBzYXZlIGR1bXAgY29weSBw",
            "YXRjaCBmbGFzaCB0YWJsZSB6ZWxkYSBkdW1wIHNuYXAgcGFnZSBtYXNrIHdpbmRvdyBjb3B5IHBhZ2Ugcm9tIG1hc2sg",
            "cGF0Y2ggcGFnZSByb20gcGFnZSB6ZWxkYSB6ZWxkYSB0YWJsZSB6ZWxkYSBydW4gc25hcCBzbmFwIHJ1biBwYWdlIHNs",
            "b3QgdGFibGUgemVsZGEgemVsZGEgYWRkIHJ1biByb20gc2xvdCBtYXNrIHNyYW0gbWFzayBzcmFtIHplbGRhIHNyYW0g",
            "YWRkIHRhYmxlIHNhdmUgcGFnZSB0YWJsZSBkdW1wIHRhYmxlIG1hc2sgcm9tIHNhdmUgc3JhbSB3aW5kb3cgc3JhbSB6",
            "ZWxkYSByb20gc3JhbSB3aW5kb3cgZHVtcCBwYWdlIGNvcHkgc2xvdCBwYXRjaCBzbG90IHJ1biB6ZWxkYSBwYWdlIHNh",
            "dmUgc3JhbSBtYXNrIHJvbSBwYWdlIG1hc2sgd2luZG93IG1hc2sgemVsZGEgcGFnZSBtYXNrIHNyYW0gdGFibGUgc2xv",
            "dCBwYXRjaCBzcmFtIGFkZCBzbG90IHBhdGNoIHJvbSBtYXNrIHNsb3Qgc2F2ZSByb20gc25hcCBzbG90IHBhZ2Ugc2xv",
            "dCBzbG90IHRhYmxlIHRhYmxlIHRhYmxlIHJvbSBzYXZlIHJ1biBjb3B5IHNhdmUgcGFnZSBjb3B5IHdpbmRvdyBzcmFt",
            "IHJ1biBzbmFwIGR1bXAgd2luZG93IHBhZ2Ugc25hcCBwYWdlIHBhZ2Ugcm9tIG1hc2sgcGFnZSB0YWJsZSByb20gdGFi",
            "bGUgc2F2ZSBhZGQgcGFnZSBjb3B5IGR1bXAgcm9tIGR1bXAgc25hcCBzbG90IGZsYXNoIHBhZ2UgbWFzayBydW4gc2xv",
            "dCBwYXRjaCBkdW1wIGR1bXAgbWFzayBydW4gc3JhbSB3aW5kb3cgc2F2ZSB3aW5kb3cgc25hcCBjb3B5IGR1bXAgc25h",
            "cCBzcmFtIHplbGRhIHplbGRhIHNhdmUgZmxhc2ggZmxhc2ggZHVtcCBmbGFzaCBkdW1wIHRhYmxlIHBhZ2Ugcm9tIHBh",
            "dGNoIHJvbSBzbmFwIHNsb3Qgc25hcCBzbG90IHNuYXAgcm9tIHBhdGNoIGR1bXAgZmxhc2ggc25hcCBzbmFwIGFkZCBw",
            "YXRjaCBtYXNrIHNyYW0gcm9tIHNuYXAgdGFibGUgc2F2ZSBwYXRjaCB0YWJsZSBwYXRjaCBjb3B5IHJ1biByb20gemVs",
            "ZGEgZmxhc2ggY29weSBzcmFtIHNhdmUgc3JhbSBzbG90IHJvbSBkdW1wIHBhdGNoIHNsb3Qgcm9tIHJ1biBtYXNrIHNs",
            "b3QgdGFibGUgbWFzayB6ZWxkYSBzbmFwIHBhZ2UgYWRkIGFkZCBtYXNrIGR1bXAgcGFnZSBwYXRjaCB0YWJsZSB6ZWxk",
            "YSBydW4gc2F2ZSBwYWdlIHNuYXAgd2luZG93IHBhdGNoIGR1bXAgcGF0Y2ggc2F2ZSB6ZWxkYSB6ZWxkYSBmbGFzaCBh",
            "ZGQgdGFibGUgcm9tIHBhZ2UgcGF0Y2ggbWFzayBmbGFzaCBjb3B5IGZsYXNoIHBhZ2Ugcm9tIHNyYW0gcm9tIHBhZ2Ug",
            "c25hcCBzbG90IGR1bXAgcGF0Y2ggYWRkIHRhYmxlIHBhZ2UgcGFnZSB0YWJsZSBwYXRjaCBtYXNrIHNhdmUgcGFnZSBy",
            "b20gcnVuIHNyYW0gdGFibGUgc2F2ZSB6ZWxkYSBzYXZlIHNsb3Qgc25hcCBzbG90IHNsb3QgemVsZGEgcnVuIGFkZCBy",
            "b20gcGF0Y2ggc2F2ZSBzbmFwIHNuYXAgc3JhbSBydW4gcGFnZSBtYXNrIGFkZCBtYXNrIHJ1biBhZGQgY29weSBzbG90",
            "IHNsb3QgbWFzayBzcmFtIHBhdGNoIHNsb3QgcGF0Y2ggemVsZGEgY29weSBjb3B5IHNsb3QgdGFibGUgYWRkIHNyYW0g",
            "c2xvdCBhZGQgdGFibGUgemVsZGEgbWFzayBmbGFzaCBwYWdlIHJ1biBkdW1wIHBhdGNoIHNsb3QgdGFibGUgc25hcCBh",
            "ZGQgemVsZGEgd2luZG93IHNuYXAgcGFnZSBjb3B5IHplbGRhIGR1bXAgYWRkIHBhZ2UgbWFzayBzbmFwIHRhYmxlIHJ1",
            "biBzbmFwIHNuYXAgc2F2ZSB3aW5kb3cgd2luZG93IHJ1biBzYXZlIHJvbSBwYWdlIHNhdmUgc2F2ZSB0YWJsZSBhZGQg",
            "d2luZG93IHdpbmRvdyBzbmFwIHNuYXAgemVsZGEgc2xvdCBkdW1wIGZsYXNoIHBhdGNoIHJ1biB3aW5kb3cgZHVtcCBy",
            "dW4gYWRkIHNsb3Qgc3JhbSB0YWJsZSB6ZWxkYSBhZGQgc3JhbSByb20gcnVuIGR1bXAgZHVtcCBhZGQgc2xvdCBkdW1w",
            "IGR1bXAgbWFzayBzYXZlIHdpbmRvdyBmbGFzaCB6ZWxkYSBhZGQgbWFzayByb20gc25hcCBzbmFwIHNuYXAgemVsZGEg",
            "Y29weSBtYXNrIHBhdGNoIHNsb3QgYWRkIHdpbmRvdyBtYXNrIGR1bXAgcm9tIHJvbSBzcmFtIGZsYXNoIHNsb3QgbWFz",
            "ayBzYXZlIHRhYmxlIHNuYXAgc3JhbSBkdW1wIHRhYmxlIHRhYmxlIHNuYXAgc3JhbSBjb3B5IHRhYmxlIHJvbSBtYXNr",
            "IHNsb3Qgc25hcCB0YWJsZSB3aW5kb3cgdGFibGUgcm9tIG1hc2sgZmxhc2ggY29weSBzYXZlIGFkZCByb20gc25hcCBy",
            "b20gemVsZGEgc2xvdCBjb3B5IHBhdGNoIHRhYmxlIHplbGRhIHRhYmxlIHplbGRhIHNyYW0gd2luZG93IHdpbmRvdyBz",
            "cmFtIHBhZ2UgcnVuIGNvcHkgd2luZG93IHJ1biBmbGFzaCB3aW5kb3cgY29weSBydW4gcGF0Y2ggcGFnZSBydW4gcm9t",
            "IHJvbSBhZGQgY29weSBjb3B5IHJvbSB6ZWxkYSBwYXRjaCB0YWJsZSBwYXRjaCBydW4gc3JhbSB3aW5kb3cgdGFibGUg",
            "c2F2ZSBmbGFzaCBwYXRjaCBkdW1wIHRhYmxlIHRhYmxlIHRhYmxlIHNuYXAgcm9tIHRhYmxlIHNhdmUgcGF0Y2ggdGFi",
            "bGUgY29weSBmbGFzaCBydW4gZHVtcCBzYXZlIHNuYXAgc3JhbSBydW4gY29weSBzcmFtIGZsYXNoIGR1bXAgY29weSB6",
            "ZWxkYSBhZGQgYWRkIHNyYW0gcm9tIHNsb3Qgc2F2ZSBydW4gemVsZGEgcGF0Y2ggZHVtcCB6ZWxkYSBzbmFwIHNuYXAg",
            "c3JhbSB6ZWxkYSBmbGFzaCBydW4gbWFzayBwYWdlIHNyYW0gcnVuIHNyYW0gZmxhc2ggcGF0Y2ggYWRkIHplbGRhIHpl",
            "bGRhIHBhZ2UgY29weSBjb3B5IHRhYmxlIHRhYmxlIHplbGRhIHBhZ2UgcGFnZSBwYXRjaCBwYXRjaCBjb3B5IHNuYXAg",
            "d2luZG93IHplbGRhIHBhZ2Ugc2F2ZSByb20gbWFzayBzbmFwIHBhdGNoIGR1bXAgcGFnZSB3aW5kb3cgdGFibGUgZHVt",
            "cCBwYWdlIHNyYW0gc25hcCBzcmFtIGZsYXNoIGFkZCBzbG90IHNuYXAgc2xvdCB0YWJsZSBwYXRjaCB6ZWxkYSBhZGQg",
            "c2xvdCB3aW5kb3cgcGFnZSBzcmFtIGFkZCByb20gc2xvdCByb20gemVsZGEgemVsZGEgc2xvdCBjb3B5IHNyYW0gc25h",
            "cCBzcmFtIGZsYXNoIGR1bXAgd2luZG93IHNhdmUgcGFnZSBzcmFtIGZsYXNoIG1hc2sgcGFnZSBjb3B5IHdpbmRvdyB3",
            "aW5kb3cgY29weSBjb3B5IHplbGRhIHNsb3Qgc25hcCB3aW5kb3cgcm9tIHplbGRhIGZsYXNoIHdpbmRvdyBydW4gdGFi",
            "bGUgZmxhc2ggcnVuIHRhYmxlIGR1bXAgc2F2ZSB0YWJsZSBzbmFwIHBhZ2Ugc2F2ZSBzbmFwIHJ1biBhZGQgemVsZGEg",
            "cGF0Y2ggZmxhc2ggcGFnZSB3aW5kb3cgcGF0Y2ggcm9tIHNsb3Qgc2F2ZSBkdW1wIHNhdmUgcm9tIHNyYW0gZmxhc2gg",
            "c25hcCBjb3B5IGZsYXNoIGFkZCBwYXRjaCBtYXNrIGFkZCBmbGFzaCBzcmFtIHNyYW0gc25hcCBwYXRjaCBzcmFtIHNs",
            "b3Qgc25hcCBzcmFtIHplbGRhIGR1bXAgbWFzayBzbG90IHNhdmUgd2luZG93IHNsb3QgZmxhc2ggcGF0Y2ggc25hcCBy",
            "b20gcm9tIHJ1biBwYWdlIHNhdmUgcGF0Y2ggd2luZG93IGFkZCBtYXNrIHdpbmRvdyBwYWdlIHJvbSB6ZWxkYSBtYXNr",
            "IHRhYmxlIHNyYW0gZmxhc2ggcGF0Y2ggY29weSB3aW5kb3cgc3JhbSB3aW5kb3cgd2luZG93IGFkZCBjb3B5IHRhYmxl",
            "IHplbGRhIHdpbmRvdyBwYWdlIHJvbSBwYWdlIHBhZ2UgdGFibGWnpiBzbmFwIHdpbmRvdyB0YWJsZSBwYXRjaCBwYWdl",
            "IHNuYXAgZmxhc2ggc2F2ZSBydW4gcnVuIHRhYmxlIHBhZ2UgZHVtcCB6ZWxkYSBwYWdlIGFkZCBhZGQgZmxhc2ggdGFi",
            "bGUgdGFibGUgcnVuIHRhYmxlIHNhdmUgYWRkIHplbGRhIGFkZCBzbmFwIHNyYW0gc3JhbSB0YWJsZSBkdW1wIHplbGRh",
            "IHNuYXAgcnVuIHNyYW0gcGF0Y2ggc2F2ZSB0YWJsZSBzYXZlIHNhdmUgYWRkIHplbGRhIGFkZCBwYXRjaCBydW4gc2F2",
            "ZSBhZGQgZHVtcCBwYXRjaCB6ZWxkYSB0YWJsZSBtYXNrIHNsb3SnowZzbmFwIHBhZ2Ugc3JhbSBjb3B5IHdpbmRvdyBt",
            "YXNrIGFkZCBkdW1wIHJvbSBwYWdlIGZsYXNoIHJ1biBzbG90IG1hc2sgZHVtcCBwYXRjaCBzcmFtIHNhdmUgc3JhbSBz",
            "cmFtIHNuYXAgdGFibGUgc2F2ZSB6ZWxkYSBzbmFwIHdpbmRvdyBkdW1wIHplbGRhIHRhYmxlIHRhYmxlIHNyYW0gcm9t",
            "IGZsYXNoIHNsb3QgY29weSBwYXRjaCBjb3B5IGNvcHkgc3JhbSBkdW1wIGFkZCBmbGFzaCB6ZWxkYSB0YWJsZSBmbGFz",
            "aCBwYXRjaCBkdW1wIGZsYXNoIHJ1biBzbmFwIHNyYW0gc25hcCBhZGQgcGF0Y2ggc2xvdCByb20gY29weSBjb3B5IHNs",
            "b3Qgc25hcCBjb3B5IHNsb3Qgc3JhbSBhZGQgZmxhc2ggZHVtcCBzYXZlIGZsYXNoIHNsb3Qgc25hcCB0YWJsZSBjb3B5",
            "IHdpbmRvdyBzbmFwIHBhZ2UgbWFzayBzcmFtIHBhdGNoIG1hc2sgc2F2ZSBhZGSnowZyb20gc2xvdCB0YWJsZSBwYWdl",
            "IHBhZ2Ugc3JhbSBzcmFtIHBhZ2UgZmxhc2ggc2xvdCByb20gcGF0Y2ggcGF0Y2ggZHVtcCBydW4gcGF0Y2ggc2xvdCBy",
            "b20gc25hcCB0YWJsZSBydW4gZHVtcCB6ZWxkYSBzbG90IGNvcHkgZmxhc2ggcnVuIHNhdmUgcGF0Y2ggcnVuIHNuYXAg",
            "c3JhbSB6ZWxkYSBkdW1wIHJvbSB6ZWxkYSByb20gcm9tIHNhdmUgemVsZGGnowVmbGFzaCByb20gcGFnZSByb20gcGFn",
            "ZSBzbG90IGZsYXNoIHNhdmUgcGFnZSBzbG90IHplbGRhIG1hc2sgZHVtcCByb20gc25hcCBhZGQgbWFzayBzp6P9C7g=",
        )
    ),
    "escapes": _decoded(
        (
            "p6P8BhwwFBVyW6ejGTW6Cy/3zKejKCN4qNvGnKejE1LcXEVJ0Kej/BO/TsxzstanoyCpdQ8itRSno4QrwT2gG92now6e",
            "e0GT2CSnoxIRNkaGlmuno2qIooRD22Gnow3i0pIcEzeno/rE1VktZaejDX6otrT/cqejdRl/2kzqrKejBZczrc6E43oB",
            "p6NmsL2k6AlVp6OZMgnRZm8ep6P9Aus9A5/1TA2no/xOhfFKeVOzp6NHkOoYCC+ip6MqXdUq1CXAp6P8KfisT2wR+qej",
            "dtCQL8fjB6ej/LVvF40pVvCno4JESzO6oE6no0NWjZYP0X+noxzC/wY8OoXuqjGnowa3BjitXZano/w66hsm4Wh4p6P8",
            "ctjZw403SKejOPxdiDaYqaej/DQDpR377eqnoznJSJsCjsano6XxY7qnvLmnoxkK7rHBQStTX85Bp6MhS5TIgPWPp6P8",
            "d98hWFKMiaej1aelo3mkpqSmpninp6SmpaenpKOneaR4o6Sio3ikpaSjo3ilpaalpnl5o6Wnp6KneKOmpKOipqOnead4",
            "eaakoqajpHimpqOkeKJ5eXiipaR4o6enpKSneHijeaKlpaSnp6SieaKlpaR4pqKmpaKleaaipqV5o6alpqWieKWnp6J5",
            "pKN4pqenpnl4pqOlp6ekpKajpXiioqajeaV5eKZ5p6enp6WlpKd4eXmieXmko6enpKd4onikp6eleaOipaZ5o6V5eaan",
            "p6KneKOieaOneKOmoqampnl5eXilo6Oio3ilpHmio6J5paSmp6eipqeno6SjpKWkeaeno6WkeaSnp6R5oqSnp6R5pKSk",
            "onikeaZ4eaeno6ajpXinp6d5eKWnp6N5pad5onmlpKampaSioqd4p6eloqR5paV4pKZ5pXl4eKenpKakeKN4p6eipnim",
            "onmkpKWjeHiko3mnp6enp6eip6ejpaZ4o6aioqenpXimp6ejo6enpqenpqWneKKkeKOjeXmjoniipHimeKV4oqZ5oqKj",
            "pKaneKWmp6eleKKmeHiipKWnp6alpKamo6ajeKSlpaWjpnl5p6enp6KmpXmieaako6d4paOnp6Z4o6enp6elp6ejp6ek",
            "o3l4eKKmpqWmpqV5pqWjpKJ5pad4pKKmpKOipXl4pKOip6eieXiipXl5pXimpHmmeKd5oqSkpqKleKOjpaKnp6Oio6Z5",
            "eXmnpw==",
        )
    ),
}
