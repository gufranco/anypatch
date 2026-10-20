from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass

from anypatch.formats.xdelta_vectors_test_support import edited, moved, text


@dataclass(frozen=True, slots=True)
class Case:
    name: str
    source: bytes
    target: bytes


def cases() -> list[Case]:
    small, wide = text(8000, 41), text(70000, 43)
    return [
        Case("edit", small, edited(small, 51, 12)),
        Case("grow", small, small + text(3000, 52)),
        Case("shrink", small, small[:5000]),
        Case("moved", wide, moved(wide, 53)),
    ]


def _decoded(chunks: tuple[str, ...]) -> bytes:
    return base64.b64decode("".join(chunks))


PATCHES: Mapping[str, bytes] = {
    "edit": _decoded(
        (
            "VlBBVAEAAIAaAAAA+AZHbGteFzVf05b2bJTZRpVaeL/fB9ef8RUwyjaCFC6/AAAAAsgBAAAAAAUG1CiJw6+ZAr4BzgEA",
            "AAUGSOOOtm3gAYySAwAABQZ6+Hzqd8MCdgYkBAAABQYHPXf3unwCTAKgCgAABQYOhgy9Dr0CkQLyDAAABQZAmvrxGKAC",
            "MwGJDwAABQSF0PJSAdDAEAAABQYnEAPXky4ByJYRAAAFBrRV/uTW5wJTAmQSAAAFBu2zgN00CwLTBL0UAAAFBoFAELDL",
            "BAKNApYZAAAFBpvLB8pRdgIXAykcAAD/AKsqU+dg3QE=",
        )
    ),
    "grow": _decoded(
        (
            "VlBBVAEAAIADAAAA+AZHbGteFzVf05b2bJTZRiDsGLDhGszyWhcPZehl0LbLCwAAAkAfAAAAAAa4C21hc2sgcGFnZSBh",
            "ZGQgcm9tIGNvcHkgc2F2ZSBzcmFtIHJ1biB0YWJsZSBjb3B5IHNsb3Qgc3JhbSBwYWdlIHBhZ2UgZHVtcCBjb3B5IHNy",
            "YW0gd2luZG93IHplbGRhIHdpbmRvdyBtYXNrIHNhdmUgZmxhc2ggc2xvdCBhZGQgcnVuIHBhZ2UgcGFnZSBjb3B5IGNv",
            "cHkgZmxhc2ggemVsZGEgbWFzayBmbGFzaCBydW4gc2F2ZSBwYXRjaCB3aW5kb3cgcnVuIHplbGRhIHJvbSBkdW1wIHJ1",
            "biBwYXRjaCBkdW1wIGR1bXAgYWRkIHNhdmUgc2F2ZSB3aW5kb3cgcGFnZSByb20gd2luZG93IHJ1biB3aW5kb3cgZHVt",
            "cCBzbG90IHNuYXAgemVsZGEgcnVuIHNhdmUgcGFnZSBwYWdlIHBhdGNoIGZsYXNoIGR1bXAgcGFnZSBmbGFzaCBzcmFt",
            "IHRhYmxlIHplbGRhIGZsYXNoIHNhdmUgemVsZGEgZHVtcCBmbGFzaCBtYXNrIHNsb3Qgd2luZG93IGR1bXAgc2xvdCBz",
            "bG90IGNvcHkgcGFnZSBzbG90IHNuYXAgYWRkIGFkZCBydW4gc2F2ZSBtYXNrIHNsb3QgemVsZGEgc25hcCBzbmFwIHNy",
            "YW0gY29weSByb20gc3JhbSBzYXZlIGR1bXAgdGFibGUgZmxhc2ggdGFibGUgc25hcCBhZGQgcnVuIHdpbmRvdyB0YWJs",
            "ZSBwYXRjaCBzbmFwIHNsb3QgdGFibGUgcGF0Y2ggcnVuIGR1bXAgZHVtcCB0YWJsZSBydW4gbWFzayB0YWJsZSB3aW5k",
            "b3cgcnVuIGR1bXAgbWFzayB6ZWxkYSB3aW5kb3cgc2xvdCBwYWdlIGNvcHkgdGFibGUgcm9tIHBhdGNoIHBhZ2Ugcm9t",
            "IGR1bXAgZHVtcCByb20gcm9tIHBhZ2Ugc25hcCB6ZWxkYSBydW4gdGFibGUgY29weSBzbmFwIGZsYXNoIHRhYmxlIHNs",
            "b3QgcGF0Y2ggcm9tIHJ1biBydW4gcm9tIHBhZ2Ugc25hcCBjb3B5IHRhYmxlIHBhZ2UgcGF0Y2ggcGF0Y2ggbWFzayBw",
            "YWdlIGR1bXAgY29weSB6ZWxkYSBjb3B5IHNuYXAgZHVtcCB6ZWxkYSByb20gcnVuIHBhdGNoIGFkZCByb20gemVsZGEg",
            "cGFnZSByb20gZHVtcCBkdW1wIHdpbmRvdyBwYWdlIHBhdGNoIHdpbmRvdyBzbG90IHNsb3QgY29weSBtYXNrIHdpbmRv",
            "dyB3aW5kb3cgemVsZGEgY29weSB3aW5kb3cgYWRkIHRhYmxlIHJvbSBtYXNrIGR1bXAgcnVuIGR1bXAgcGFnZSBzbmFw",
            "IHplbGRhIG1hc2sgdGFibGUgZHVtcCB0YWJsZSBzYXZlIGFkZCBkdW1wIHNyYW0gZmxhc2ggbWFzayByb20gemVsZGEg",
            "cm9tIGFkZCBzYXZlIHNsb3Qgc2F2ZSBhZGQgcGFnZSBydW4gcGFnZSBzYXZlIHplbGRhIHNyYW0gc2F2ZSBwYWdlIHNy",
            "YW0gcGFnZSBzbG90IHdpbmRvdyB0YWJsZSBzcmFtIHRhYmxlIGFkZCBzcmFtIHNsb3QgbWFzayBtYXNrIGFkZCBzcmFt",
            "IHBhZ2UgZmxhc2ggZHVtcCBmbGFzaCB6ZWxkYSBzbG90IGZsYXNoIHNhdmUgc25hcCBwYXRjaCBzcmFtIHNsb3Qgc2xv",
            "dCBjb3B5IHBhdGNoIHBhZ2Ugc2F2ZSBtYXNrIHNuYXAgZmxhc2ggZmxhc2ggY29weSBmbGFzaCBhZGQgcnVuIGFkZCBh",
            "ZGQgd2luZG93IHNuYXAgemVsZGEgbWFzayBzcmFtIG1hc2sgcnVuIHNuYXAgc3JhbSB0YWJsZSBhZGQgc2F2ZSBkdW1w",
            "IGR1bXAgd2luZG93IGZsYXNoIGNvcHkgc25hcCBjb3B5IHNyYW0gcnVuIHJ1biBhZGQgcm9tIHNyYW0gcm9tIGFkZCB6",
            "ZWxkYSBzbG90IGFkZCB3aW5kb3cgcm9tIHNsb3Qgc25hcCB0YWJsZSBzcmFtIG1hc2sgbWFzayBkdW1wIGR1bXAgZmxh",
            "c2ggbWFzayBwYWdlIHBhZ2Ugc25hcCB3aW5kb3cgemVsZGEgbWFzayBzcmFtIGR1bXAgcm9tIHNsb3QgYWRkIHRhYmxl",
            "IHdpbmRvdyBmbGFzaCBhZGQgYWRkIHJvbSBhZGQgcGF0Y2ggc25hcCBzcmFtIHNyYW0gdGFibGUgc2F2ZSBtYXNrIHBh",
            "Z2UgcnVuIGR1bXAgZHVtcCB0YWJsZSB6ZWxkYSBkdW1wIGNvcHkgc2xvdCByb20gemVsZGEgdGFibGUgcnVuIHdpbmRv",
            "dyBydW4gc3JhbSBkdW1wIHNuYXAgZHVtcCB3aW5kb3cgc3JhbSBwYXRjaCBydW4gcnVuIGFkZCBwYXRjaCBzbmFwIHJv",
            "bSBwYXRjaCByb20gbWFzayBzbmFwIHNsb3Qgd2luZG93IHplbGRhIHplbGRhIHBhZ2UgcGF0Y2ggZmxhc2ggc3JhbSBz",
            "bmFwIG1hc2sgcGFnZSBhZGQgcnVuIHNyYW0gcnVuIHplbGRhIHBhdGNoIHplbGRhIHRhYmxlIHNsb3Qgc3JhbSBzbG90",
            "IHNyYW0gcnVuIHNhdmUgY29weSByb20gc3JhbSBtYXNrIHNhdmUgemVsZGEgZmxhc2ggcGF0Y2ggc25hcCB6ZWxkYSBz",
            "bmFwIGR1bXAgdGFibGUgcm9tIHdpbmRvdyB3aW5kb3cgbWFzayB6ZWxkYSBzbmFwIHJ1biBjb3B5IHBhZ2UgYWRkIHJ1",
            "biBmbGFzaCBzYXZlIGNvcHkgemVsZGEgYWRkIHJ1biBzYXZlIGR1bXAgc25hcCBtYXNrIHdpbmRvdyBzYXZlIGR1bXAg",
            "cm9tIHJvbSBzcmFtIGFkZCBzcmFtIG1hc2sgc2xvdCBhZGQgc2F2ZSBmbGFzaCB0YWJsZSBjb3B5IHdpbmRvdyBzYXZl",
            "IHplbGRhIHRhYmxlIHNyYW0gcnVuIGFkZCBhZGQgc2F2ZSBzYXZlIHBhdGNoIHBhZ2UgY29weSBtYXNrIHJvbSB0YWJs",
            "ZSByb20gY29weSBhZGQgd2luZG93IHdpbmRvdyBmbGFzaCBzYXZlIHNyYW0gcnVuIHdpbmRvdyBtYXNrIGNvcHkgbWFz",
            "ayBwYXRjaCBkdW1wIHNhdmUgc25hcCBkdW1wIHJ1biBzYXZlIHJvbSBzcmFtIGZsYXNoIHplbGRhIHNhdmUgcGFnZSB0",
            "YWJsZSBwYXRjaCB0YWJsZSBzYXZlIHBhdGNoIHdpbmRvdyBzbmFwIGFkZCB6ZWxkYSBydW4gc3JhbSBkdW1wIGNvcHkg",
            "Y29weSByb20gd2luZG93IGFkZCBwYXRjaCByb20gc2F2ZSB0YWJsZSBtYXNrIHplbGRhIHJ1biBzYXZlIG1hc2sgdGFi",
            "bGUgcnVuIGFkZCBwYWdlIHJvbSBydW4gY29weSBjb3B5IGFkZCBmbGFzaCBmbGFzaCBwYWdlIG1hc2sgdGFibGUgc2xv",
            "dCBwYXRjaCBzYXZlIHNuYXAgZmxhc2ggbWFzayBmbGFzaCBzcmFtIGFkZCBydW4gZmxhc2ggc25hcCB3aW5kb3cgY29w",
            "eSBhZGQgcm9tIHNhdmUgdGFibGUgemVsZGEgYWRkIHJ1biBwYXRjaCBwYXRjaCB3aW5kb3cgd2luZG93IGZsYXNoIHNy",
            "YW0gZmxhc2ggZmxhc2ggdGFibGUgd2luZG93IHBhdGNoIGFkZCByb20gY29weSByb20gc2xvdCBkdW1wIHJvbSB0YWJs",
            "ZSBmbGFzaCBzcmFtIHBhZ2UgYWRkIHNuYXAgbWFzayByb20gc25hcCBzbmFwIGFkZCByb20gemVsZGEgcGF0Y2ggcm9t",
            "IHJvbSBzcmFtIG1hc2sgc2F2ZSB6Zf8AqypT52DdAQ==",
        )
    ),
    "shrink": _decoded(
        (
            "VlBBVAEAAIACAAAA+AZHbGteFzVf05b2bJTZRpLUOUxDmsKeC0zcQTv4S5QQAAAAAogTAAAAAP8AqypT52DdAQ==",
        )
    ),
    "moved": _decoded(
        (
            "VlBBVAEAAIBVAAAA7gpIBv8hiznJVj7vOQVdeZv3r/0Gj5x9umyWXf/2Tdl6FgAAAngFJVsAAAUGGX/aTOqsAncHo2AA",
            "AAUGK8E9oBvdAZAgaAAABQYHPXf3unwCUBG2aAAABQXHbhE/7QI6BQt6AAAFBr9OzHOy1gIhCEt/AAAFBmFthdDyUgKF",
            "FXKHAAAFBu2zgN00CwIiAv2cAAAFBkCa+vEYoAI3BCWfAAAFBg6GDL0OvQJsAmKjAAAFBjIJ0WZvHgGV1KUAAAUGOVJl",
            "K8RfAgcDb6YAAAUGtwY4rV2WAl8EfKkAAAUGpcTVWS1lAhkC4a0AAAUG+KxPbBH6Ao4JALAAAAUG5mrsGODKAhsElLkA",
            "AAUGREszuqBOAjcDtb0AAAUGm8sHylF2AsgB8sAAAAUYnntBk9gkc25hcCBtYXNrIHplJxAD15MuAlQS0sIAAAUGtFX+",
            "5NbnAt0DLNUAAAUG3yFYUoyJAvgBD9kAAAUG1CiJw6+ZAiIEDdsAAAUGxpdhOAYXAgIBNd8AAAUGWiXxC50RAr0KPeAA",
            "AAUGevh86nfDAgIVAOsAAAVzjDreP6j0bGUgY29weSBzbG90IGR1bXAgd2luZG93IHJvbSByb20gYWRkIGNvcHkgc2xv",
            "dCB6ZWxkYSBmbGFzaCBwYXRjaCBhZGQgZHVtcCBzbG90IHBhZ2UgdGFibGUgc3JhbSByb20gZmxhc36otrT/cgIVAnUA",
            "AQAFBmxnU1/OQQLgDpACAQAC/QEAAAAABQaF8Up5U7MC5wgDAgAABQbxY7qnvLkBmvAKAAAFBs3g9f5bWAI/BJALAAAF",
            "BlLcXEVJ0AF01Q8AAAUGrQ1qHoGmAqsETxAAAAUGS5TIgPWPAgYMABUAAAUGc6/oJSOCAhgDDCEAAAUGZB6/mnoBAnkh",
            "KiQAAAUGk4JzBPw1AuoEqUUAAAUG//TjMmU7AlsFmUoAAAUG2NnDjTdIApoI+k8AAAUGETZGhpZrAosCmlgAAAaIE2R1",
            "bXAgbWFzayB3aW5kb3cgZHVtcCB6ZWxkYSBwYWdlIHdpbmRvdyBhZGQgcm9tIHNhdmUgc2xvdCB3aW5kb3cgcm9tIHRh",
            "YmxlIGR1bXAgZmxhc2ggd2luZG93IHNhdmUgYWRkIHBhZ2UgcGF0Y2ggcm9tIHJvbSB6ZWxkYSBzcmFtIHBhdGNoIHNu",
            "YXAgc2xvdCBtYXNrIGZsYXNoIGNvcHkgbWFzayBtYXNrIGZsYXNoIHNhdmUgcGF0Y2ggd2luZG93IGR1bXAgc25hcCB6",
            "ZWxkYSBwYXRjaCB3aW5kb3cgY29weSBzbG90IHBhZ2UgcGFnZSBmbGFzaCByb20gdGFibGUgdGFibGUgc3JhbSB0YWJs",
            "ZSBzcmFtIGR1bXAgdGFibGUgc2F2ZSBzbmFwIGFkZCBzYXZlIHNhdmUgYWRkIG1hc2sgdGFibGUgYWRkIGR1bXAgemVs",
            "ZGEgc3JhbSBzbG90IHNsb3QgZmxhc2ggZHVtcCBzbG90IHBhZ2Ugd2luZG93IGZsYXNoIHBhdGNoIHNhdmUgbWFzayBk",
            "dW1wIHBhZ2UgY29weSBwYWdlIHNhdmUgd2luZG93IHNuYXAgZHVtcCByb20gbWFzayBydW4gc2F2ZSBydW4gbWFzayBm",
            "bGFzaCBmbGFzaCB3aW5kb3cgc25hcCB6ZWxkYSBwYWdlIGR1bXAgcnVuIHplbGRhIGZsYXNoIG1hc2sgY29weSBzbG90",
            "IHJvbSBtYXNrIHNuYXAgemVsZGEgcGF0Y2ggY29weSBwYWdlIGFkZCBzcmFtIHJ1biBydW4gemVsZGEgcnVuIGFkZCB6",
            "ZWxkYSBkdW1wIHNuYXAgY29weSBzcmFtIHNuYXAgc2xvdCBkdW1wIHBhZ2Ugc25hcCBwYXRjaCBydW4gZmxhc2ggY29w",
            "eSBzYXZlIHNuYXAgZHVtcCB6ZWxkYSBzbG90IHBhdGNoIHJvbSBhZGQgdGFibGUgcGFnZSB3aW5kb3cgcnVuIGR1bXAg",
            "emVsZGEgemVsZGEgcGFnZSBydW4gbWFzayB6ZWxkYSBwYWdlIGZsYXNoIHBhZ2UgbWFzayBhZGQgc25hcCByb20gc3Jh",
            "bSByb20gc25hcCBzbmFwIHRhYmxlIGFkZCBtYXNrIG1hc2sgc3JhbSB0YWJsZSBjb3B5IHNyYW0gZHVtcCBydW4gd2lu",
            "ZG93IHBhZ2UgemVsZGEgemVsZGEgcGFnZSBmbGFzaCB3aW5kb3cgcm9tIHNsb3Qgc25hcCBhZGQgc3JhbSBmbGFzaCBt",
            "YXNrIHJ1biBtYXNrIHNuYXAgbWFzayBydW4gbWFzayBzbG90IHNhdmUgZmxhc2ggc3JhbSBzYXZlIHBhdGNoIGFkZCBz",
            "bG90IHNuYXAgc2xvdCB3aW5kb3cgc2F2ZSBkdW1wIHJvbSB3aW5kb3cgcnVuIHJvbSB0YWJsZSByb20gc25hcCB0YWJs",
            "ZSBwYXRjaCB0YWJsZSBzYXZlIHJ1biBzbG90IHNyYW0gcnVuIGR1bXAgc25hcCBmbGFzaCB0YWJsZSBzbG90IGFkZCBh",
            "ZGQgZmxhc2ggc2F2ZSBkdW1wIHRhYmxlIGNvcHkgc2F2ZSBzbmFwIHNsb3QgcGF0Y2ggcm9tIHBhZ2Ugc3JhbSBzYXZl",
            "IGR1bXAgZHVtcCB3aW5kb3cgc3JhbSBkdW1wIHJvbSBwYWdlIHBhZ2UgdGFibGUgc2F2ZSB6ZWxkYSBwYXRjaCByb20g",
            "Zmxhc2ggZmxhc2ggcm9tIHNyYW0gbWFzayBwYWdlIHBhZ2Ugc2F2ZSBhZGQgZmxhc2ggbWFzayBkdW1wIHNuYXAgd2lu",
            "ZG93IHJvbSBtYXNrIHNyYW0gc3JhbSBzYXZlIHplbGRhIG1hc2sgemVsZGEgZHVtcCBwYXRjaCBmbGFzaCBmbGFzaCBz",
            "bG90IGR1bXAgc2xvdCByb20gcGFnZSB0YWJsZSByb20gemVsZGEgc2xvdCBzbG90IG1hc2sgc25hcCBzYXZlIG1hc2sg",
            "YWRkIG1hc2sgY29weSBzYXZlIGFkZCBkdW1wIGR1bXAgbWFzayB3aW5kb3cgcGFnZSBtYXNrIHRhYmxlIG1hc2sgYWRk",
            "IGR1bXAgZmxhc2ggc2xvdCB6ZWxkYSBwYXRjaCByb20gcm9tIHNuYXAgZmxhc2ggY29weSBwYWdlIGR1bXAgdGFibGUg",
            "c2xvdCByb20gbWFzayBydW4gZmxhc2ggc3JhbSBzcmFtIHNsb3Qgc25hcCBjb3B5IHplbGRhIHJ1biBhZGQgc25hcCBy",
            "dW4gZmxhc2ggd2luZG93IGZsYXNoIGR1bXAgbWFzayBwYWdlIG1hc2sgd2luZG93IHNhdmUgc3JhbSBmbGFzaCByb20g",
            "d2luZG93IHplbGRhIGNvcHkgc2xvdCBzcmFtIHNuYXAgbWFzayBtYXNrIGR1bXAgc3JhbSBwYWdlIHNuYXAgdGFibGUg",
            "Y29weSBzYXZlIGR1bXAgY29weSBwYWdlIHJ1biB3aW5kb3cgZmxhc2ggdGFibGUgcGF0Y2ggcGFnZSBjb3B5IHNuYXAg",
            "c2xvdCBkdW1wIGR1bXAgc2xvdCBkdW1wIHJvbSBwYXRjaCB3aW5kb3cgYWRkIGR1bXAgcGFnZSBwYXRjaCBzbmFwIHNh",
            "dmUgemVsZGEgcGFnZSBzbmFwIHBhZ2UgbWFzayBzbG90IGFkZCB3aW5kb3cgd2luZG93IGFkZCBzbmFwIHBhZ2UgZmxh",
            "c2ggemVsZGEgcnVuIGZsYXNoIGZsYXNoIHBhdGNoIHNhdmUgemVsZGEgcGFnZSByb20gcGF0Y2ggc2F2ZSBtYXNrIHBh",
            "Z2UgYWRkIHplbGRhIHNhdmUgc3JhbSBydW4gc25hcCBzYXZlIHdpbmRvdyBkdW1wIG1hc2sgc2xvdCByb20gc2F2ZSB0",
            "YWJsZSBzbG90IHplbGRhIHdpbmRvdyBwYXRjaCBzbmFwIHNuYXAgdGFibGUgcGF0Y2ggd2luZG93IGZsYXNoIHJvbSBw",
            "YXRjaCBzcmFtIHJ1biB3aW5kb3cgYWRkIHNuYXAgc2xvdCBzbG90IGZsYXNoIGZsYXNoIHplbGRhIHNyYW0gcGF0Y2gg",
            "cGF0Y2ggdGFibGUgZmxhc2ggc3JhbSBwYWdlIHdpbmRvdyBhZGQgY29weSBjb3B5IHJvbSBwYWdlIGNvcHkgZmxhc2gg",
            "cm9tIHNsb3QgZHVtcCB0YWJsZSBwYWdlIHBhdGNoIHJ1biBydW4gemVsZGEgc2xvdCByb20gemVsZGEgemVsZGEgbWFz",
            "ayBmbGFzaCBhZGQgZmxhc2ggZHVtcCBjb3B5IGZsYXNoIHplbGRhIHNsb3QgemVsZGEgd2luZG93IGNvcHkgYWRkIHBh",
            "dGNoIHJ1biBwYWdlIHBhZ2UgZmxhc2ggc2F2ZSBwYWdlIHNsb3Qgcm9tIHJvbSBkdW1wIHNuYXAgcGF0Y2ggZmxhc2gg",
            "emVsZGEgd2luZG93IHNhdmUgcGF0Y2ggdGFibGUgcGFnZSBydW4gcnVuIHplbGRhIHNhdmUgbWFzayBwYXRjaCBtYXNr",
            "IHBhdGNoIHNhdmUgcm9tIGZsYXNoIHBhdGNoIG1hc2sgc3JhbSB6ZWxkYSByb20gYWRkIHNhdmUgc25hcCBhZGQgcm9t",
            "IHJvbSBjb3B5IHplbGRhIHplbGRhIHNyYW0gdGFibGUgZHVtcCB0YWJsZSBwYXRjaCBzbG90IHdpbmRvdyBzcmFtIHdp",
            "bmRvdyBzbG90IHdpbmRvdyBzbG90IHJ1biBzcmFtIGFkZCBzbG90IHBhdGNoIHNhdmUgZHVtcCB3aW5kb3cgY29weSBt",
            "YXNrIHNsb3QgY29weSBtYXNrIGZsYXNoIHNuYXAgcGFnZSBjb3B5IHNsb3QgYWRkIGR1bXAgbWFzayBwYXRjaCBzbmFw",
            "IGNvcHkgc2F2ZSBhZGQgd2luZG93IHBhZ2Ugd2luZG93IGNvcHkgdGFibGUgbWFzayByb20gd2luZG93IHJvbSB3aW5k",
            "b3cgZmxhc2ggc3JhbSB0YWJsZSBhZGQgZHVtcCBzYXZlIHNsb3Qgcm9tIHNhdmUgc3JhbSBhZGQgdGFibGUgc3JhbSB6",
            "ZWxkYSByb20gY29weSBjb3B5IHNhdmUgcnVuIHNhdmUgc3JhbSBkdW1wIGR1bXAgZHVtcCBzbmFwIHBhdGNoIHBhZ2Ug",
            "Y29weSBtYXNrIHJ1biBwYXRjaCBzYXZlIHNyYW0gc2F2ZSBzbG90IHplbGRhIHJ1biByb20gYWRkIGZsYXNoIHJ1biBz",
            "bG90IHNsb3QgcGFnZSBydW4gYWRkIHRhYmxlIG1hc2sgemVsZGEgd2luZG93IHNsb3QgdGFibGUgc25hcCBzYXZlIHJ1",
            "biBhZGQgZHVtcCB6ZWxkYSBydW4gcGF0Y2ggY29weSBmbGFzaCBzbG90IG1hc2sgc2xvdCBzYXZlIGFkZCBydW4gcm9t",
            "IHBhZ2UgcGF0Y2ggdGFibGUgcnVuIHJ1biBwYWdlIHplbGRhIGR1bXAgc3JhbSB0YWJsZSBzcmFtIHJ1biB6ZWxkYSBz",
            "YXZlIHRhYmxlIGNvcHkgc25hcCBzcmFtIG1hc2sgcm9tIG1hc2sgc2F2ZSBzbmFwIGNvcHkgd2luZG93IHNuYXAgcGF0",
            "Y2ggc2F2ZSB3aW5kb3cgcGF0Y2ggY29weSB0YWJsZSBjb3B5IHNyYW0gcGF0Y2ggcm9tIHdpbmRvdyBzbG90IHJvbSBj",
            "b3B5IGR1bXAgYWRkIHNsb3QgYWRkIGR1bXAgd2luZG93IG1hc2sgcm9tIHBhdGNoIHBhdGNoIHNhdmUgemVsZGEgcm9t",
            "IHJ1biBmbGFzaCBzYXZlIHplbGRhIHBhZ2Ugc3JhbSBhZGQgcGF0Y2ggc2xvdCBkdW1wIHJvbSBhZGQgd2luZG93IGR1",
            "bXAgYWRkIGZsYXNoIHJ1biBwYXRjaCBhZGQgYWRkIHplbGRhIHJvbSBkdW1wIHBhdGNoIHNhdmUgcm9tIHdpbmRvdyBz",
            "YXZlIHBhZ2UgY29weSBwYWdlIHNuYXAgcGFnZSBtYXNrIGFkZCBkdW1wIHNuYXAgc2xvdCByb20gdGFibGUgc2F2ZSBh",
            "ZGQgcnVuIHdpbmRvdyBzYXZlIHdpbmRvdyBjb3B5IG1hc2sgcGF0Y2ggd2luZG93IHJvbSByb20gc25hcCBzYXZlIHdp",
            "bmRvdyBzbG90IHBhZ2Ugcm9tIHplbGRhIHJ1biBmbGFzaCBtYXNrIHBhZ2Ugc25hcCB0YWJsZSBzbmFwIHJ1biBjb3B5",
            "IHNsb3QgcGF0Y2ggZmxhc2ggcGFnZSBtYXNrIHNhdmUgc25hcCBzcmFtIHJvbSB6ZWxkYSB3aW5kb3cgbWFzayBzYXZl",
            "IHNyYW0gYWRkIGR1bXAgZHVtcCBzbmFwIHdpbmRvdyB3aW5kb3cgY29weSBzYXZlIGFkZCBzYXZlIGFkZCBzbmFwIHNh",
            "dmUgcnVuIHdpbmRvdyBkdW1wIGR1bXAgbWFzayBwYXRjaCBjb3B5IHRhYmxlIHBhdGNoIHBhZ2Ugc25hcCB3aW5kb3cg",
            "dGFibGUgemVsZGEgcGFnZSBzbG90IHNuYXAgemVsZGEgc2xvdCB3aW5kb3cgcGFnZSB0YWJsZSBzbmFwIHNyYW0gcGF0",
            "Y2ggemVsZGEgYWRkIHBhdGNoIHBhdGNoIGZsYXNoIG1hc2sgc2F2ZSBzcmFtIHNhdmUgc2xvdCBzbmFwIHNsb3QgemVs",
            "ZGEgc3JhbSBkdW1wIHplbGRhIHNuYXAgZmxhc2ggZmxhc2ggYWRkIHBhdGNoIGR1bXAgcGF0Y2ggc2xvdCB6ZWxkYSB3",
            "aW5kb3cgc25hcCB6ZWxkYSBzYXZlIGR1bXAgcm9tIGR1bXAgbWFzayByb20gc2xvdCBzbmFwIHBhZ2Ugd2luZG93IHdp",
            "bmRvdyBkdW1wIGR1bXAgcnVuIHNyYW0gbWFzayBydW4gc2xvdCBkdW1wIGFkZCBwYWdlIHNhdmUgYWRkIHJvbSBzbmFw",
            "IHNyYW0gZHVtcCBydW4gbWFzayBzYXZlIGNvcHkgc2F2ZSBwYWdlIHNyYW0gc2F2ZSBydW4gc25hcCBmbGFzaCBwYWdl",
            "IHNhdmUgcGF0Y2ggYWRkIHdpbmRvdyBydW4gZmxhc2ggc3JhbSBydW4gd2luZG93IHBhdGNoIHNuYXAgd2luZG93IG1h",
            "c2sgc25hcCBjb3B5IHdpbmRvdyBwYWdlIHNuYXAgcGFnZSBzbmFwIHNsb3QgcGFnZSBtYXNrIHNhdmUgdGFibGUgcm9t",
            "IGR1bXAgemVsZGEgc2xvdCBmbGFzaCByb20gYWRkIGR1bXAgZmxhc2ggdGFibGUgbWFzayBzbmFwIGFkZCByb20gcm9t",
            "IG1hc2sgc2xvdCBzbmFwIG1hc2sgYWRkIHNyYW0gZmxhc2ggcGFnZSBydW4gc2xvdCB6ZWxkYSBzYXZlIGR1bXAgc2F2",
            "ZSBjb3B5IGR1bXAgYWRkIHNyYW0gZHVtcCB0YWJsZSBzYXZlIHNuYXAgcnVuIHJ1biBhZGQgYWRkIHBhdGNoIG1hc2sg",
            "Zmxhc2ggbWFzayBzcmFtIGZsYXNoIHNsb3QgZmxhAgIH6AMAAAUG8WO6p7y5AZrwCgAABQbN4PX+W1gCEASQCwAA/wCr",
            "KlPnYN0B",
        )
    ),
}

CRC_EDIT = _decoded(
    (
        "VlBBVAEAAAAaAAAAalzjDQYR9n6/AAAAAsgBAAAAAAUG1CiJw6+ZAr4BzgEAAAUGSOOOtm3gAYySAwAABQZ6+Hzqd8MC",
        "dgYkBAAABQYHPXf3unwCTAKgCgAABQYOhgy9Dr0CkQLyDAAABQZAmvrxGKACMwGJDwAABQSF0PJSAdDAEAAABQYnEAPX",
        "ky4ByJYRAAAFBrRV/uTW5wJTAmQSAAAFBu2zgN00CwLTBL0UAAAFBoFAELDLBAKNApYZAAAFBpvLB8pRdgIXAykcAAD/",
        "gDIXuedg3QE=",
    )
)
EDIT_AND_MOVED = _decoded(
    (
        "VlBBVAIAAIAaAAAA+AZHbGteFzVf05b2bJTZRpVaeL/fB9ef8RUwyjaCFC6/AAAAAsgBAAAAAAUG1CiJw6+ZAr4BzgEA",
        "AAUGSOOOtm3gAYySAwAABQZ6+Hzqd8MCdgYkBAAABQYHPXf3unwCTAKgCgAABQYOhgy9Dr0CkQLyDAAABQZAmvrxGKAC",
        "MwGJDwAABQSF0PJSAdDAEAAABQYnEAPXky4ByJYRAAAFBrRV/uTW5wJTAmQSAAAFBu2zgN00CwLTBL0UAAAFBoFAELDL",
        "BAKNApYZAAAFBpvLB8pRdgIXAykcAAD/gDIXuedg3QFVAAAA7gpIBv8hiznJVj7vOQVdeZv3r/0Gj5x9umyWXf/2Tdl6",
        "FgAAAngFJVsAAAUGGX/aTOqsAncHo2AAAAUGK8E9oBvdAZAgaAAABQYHPXf3unwCUBG2aAAABQXHbhE/7QI6BQt6AAAF",
        "Br9OzHOy1gIhCEt/AAAFBmFthdDyUgKFFXKHAAAFBu2zgN00CwIiAv2cAAAFBkCa+vEYoAI3BCWfAAAFBg6GDL0OvQJs",
        "AmKjAAAFBjIJ0WZvHgGV1KUAAAUGOVJlK8RfAgcDb6YAAAUGtwY4rV2WAl8EfKkAAAUGpcTVWS1lAhkC4a0AAAUG+KxP",
        "bBH6Ao4JALAAAAUG5mrsGODKAhsElLkAAAUGREszuqBOAjcDtb0AAAUGm8sHylF2AsgB8sAAAAUYnntBk9gkc25hcCBt",
        "YXNrIHplJxAD15MuAlQS0sIAAAUGtFX+5NbnAt0DLNUAAAUG3yFYUoyJAvgBD9kAAAUG1CiJw6+ZAiIEDdsAAAUGxpdh",
        "OAYXAgIBNd8AAAUGWiXxC50RAr0KPeAAAAUGevh86nfDAgIVAOsAAAVzjDreP6j0bGUgY29weSBzbG90IGR1bXAgd2lu",
        "ZG93IHJvbSByb20gYWRkIGNvcHkgc2xvdCB6ZWxkYSBmbGFzaCBwYXRjaCBhZGQgZHVtcCBzbG90IHBhZ2UgdGFibGUg",
        "c3JhbSByb20gZmxhc36otrT/cgIVAnUAAQAFBmxnU1/OQQLgDpACAQAC/QEAAAAABQaF8Up5U7MC5wgDAgAABQbxY7qn",
        "vLkBmvAKAAAFBs3g9f5bWAI/BJALAAAFBlLcXEVJ0AF01Q8AAAUGrQ1qHoGmAqsETxAAAAUGS5TIgPWPAgYMABUAAAUG",
        "c6/oJSOCAhgDDCEAAAUGZB6/mnoBAnkhKiQAAAUGk4JzBPw1AuoEqUUAAAUG//TjMmU7AlsFmUoAAAUG2NnDjTdIApoI",
        "+k8AAAUGETZGhpZrAosCmlgAAAaIE2R1bXAgbWFzayB3aW5kb3cgZHVtcCB6ZWxkYSBwYWdlIHdpbmRvdyBhZGQgcm9t",
        "IHNhdmUgc2xvdCB3aW5kb3cgcm9tIHRhYmxlIGR1bXAgZmxhc2ggd2luZG93IHNhdmUgYWRkIHBhZ2UgcGF0Y2ggcm9t",
        "IHJvbSB6ZWxkYSBzcmFtIHBhdGNoIHNuYXAgc2xvdCBtYXNrIGZsYXNoIGNvcHkgbWFzayBtYXNrIGZsYXNoIHNhdmUg",
        "cGF0Y2ggd2luZG93IGR1bXAgc25hcCB6ZWxkYSBwYXRjaCB3aW5kb3cgY29weSBzbG90IHBhZ2UgcGFnZSBmbGFzaCBy",
        "b20gdGFibGUgdGFibGUgc3JhbSB0YWJsZSBzcmFtIGR1bXAgdGFibGUgc2F2ZSBzbmFwIGFkZCBzYXZlIHNhdmUgYWRk",
        "IG1hc2sgdGFibGUgYWRkIGR1bXAgemVsZGEgc3JhbSBzbG90IHNsb3QgZmxhc2ggZHVtcCBzbG90IHBhZ2Ugd2luZG93",
        "IGZsYXNoIHBhdGNoIHNhdmUgbWFzayBkdW1wIHBhZ2UgY29weSBwYWdlIHNhdmUgd2luZG93IHNuYXAgZHVtcCByb20g",
        "bWFzayBydW4gc2F2ZSBydW4gbWFzayBmbGFzaCBmbGFzaCB3aW5kb3cgc25hcCB6ZWxkYSBwYWdlIGR1bXAgcnVuIHpl",
        "bGRhIGZsYXNoIG1hc2sgY29weSBzbG90IHJvbSBtYXNrIHNuYXAgemVsZGEgcGF0Y2ggY29weSBwYWdlIGFkZCBzcmFt",
        "IHJ1biBydW4gemVsZGEgcnVuIGFkZCB6ZWxkYSBkdW1wIHNuYXAgY29weSBzcmFtIHNuYXAgc2xvdCBkdW1wIHBhZ2Ug",
        "c25hcCBwYXRjaCBydW4gZmxhc2ggY29weSBzYXZlIHNuYXAgZHVtcCB6ZWxkYSBzbG90IHBhdGNoIHJvbSBhZGQgdGFi",
        "bGUgcGFnZSB3aW5kb3cgcnVuIGR1bXAgemVsZGEgemVsZGEgcGFnZSBydW4gbWFzayB6ZWxkYSBwYWdlIGZsYXNoIHBh",
        "Z2UgbWFzayBhZGQgc25hcCByb20gc3JhbSByb20gc25hcCBzbmFwIHRhYmxlIGFkZCBtYXNrIG1hc2sgc3JhbSB0YWJs",
        "ZSBjb3B5IHNyYW0gZHVtcCBydW4gd2luZG93IHBhZ2UgemVsZGEgemVsZGEgcGFnZSBmbGFzaCB3aW5kb3cgcm9tIHNs",
        "b3Qgc25hcCBhZGQgc3JhbSBmbGFzaCBtYXNrIHJ1biBtYXNrIHNuYXAgbWFzayBydW4gbWFzayBzbG90IHNhdmUgZmxh",
        "c2ggc3JhbSBzYXZlIHBhdGNoIGFkZCBzbG90IHNuYXAgc2xvdCB3aW5kb3cgc2F2ZSBkdW1wIHJvbSB3aW5kb3cgcnVu",
        "IHJvbSB0YWJsZSByb20gc25hcCB0YWJsZSBwYXRjaCB0YWJsZSBzYXZlIHJ1biBzbG90IHNyYW0gcnVuIGR1bXAgc25h",
        "cCBmbGFzaCB0YWJsZSBzbG90IGFkZCBhZGQgZmxhc2ggc2F2ZSBkdW1wIHRhYmxlIGNvcHkgc2F2ZSBzbmFwIHNsb3Qg",
        "cGF0Y2ggcm9tIHBhZ2Ugc3JhbSBzYXZlIGR1bXAgZHVtcCB3aW5kb3cgc3JhbSBkdW1wIHJvbSBwYWdlIHBhZ2UgdGFi",
        "bGUgc2F2ZSB6ZWxkYSBwYXRjaCByb20gZmxhc2ggZmxhc2ggcm9tIHNyYW0gbWFzayBwYWdlIHBhZ2Ugc2F2ZSBhZGQg",
        "Zmxhc2ggbWFzayBkdW1wIHNuYXAgd2luZG93IHJvbSBtYXNrIHNyYW0gc3JhbSBzYXZlIHplbGRhIG1hc2sgemVsZGEg",
        "ZHVtcCBwYXRjaCBmbGFzaCBmbGFzaCBzbG90IGR1bXAgc2xvdCByb20gcGFnZSB0YWJsZSByb20gemVsZGEgc2xvdCBz",
        "bG90IG1hc2sgc25hcCBzYXZlIG1hc2sgYWRkIG1hc2sgY29weSBzYXZlIGFkZCBkdW1wIGR1bXAgbWFzayB3aW5kb3cg",
        "cGFnZSBtYXNrIHRhYmxlIG1hc2sgYWRkIGR1bXAgZmxhc2ggc2xvdCB6ZWxkYSBwYXRjaCByb20gcm9tIHNuYXAgZmxh",
        "c2ggY29weSBwYWdlIGR1bXAgdGFibGUgc2xvdCByb20gbWFzayBydW4gZmxhc2ggc3JhbSBzcmFtIHNsb3Qgc25hcCBj",
        "b3B5IHplbGRhIHJ1biBhZGQgc25hcCBydW4gZmxhc2ggd2luZG93IGZsYXNoIGR1bXAgbWFzayBwYWdlIG1hc2sgd2lu",
        "ZG93IHNhdmUgc3JhbSBmbGFzaCByb20gd2luZG93IHplbGRhIGNvcHkgc2xvdCBzcmFtIHNuYXAgbWFzayBtYXNrIGR1",
        "bXAgc3JhbSBwYWdlIHNuYXAgdGFibGUgY29weSBzYXZlIGR1bXAgY29weSBwYWdlIHJ1biB3aW5kb3cgZmxhc2ggdGFi",
        "bGUgcGF0Y2ggcGFnZSBjb3B5IHNuYXAgc2xvdCBkdW1wIGR1bXAgc2xvdCBkdW1wIHJvbSBwYXRjaCB3aW5kb3cgYWRk",
        "IGR1bXAgcGFnZSBwYXRjaCBzbmFwIHNhdmUgemVsZGEgcGFnZSBzbmFwIHBhZ2UgbWFzayBzbG90IGFkZCB3aW5kb3cg",
        "d2luZG93IGFkZCBzbmFwIHBhZ2UgZmxhc2ggemVsZGEgcnVuIGZsYXNoIGZsYXNoIHBhdGNoIHNhdmUgemVsZGEgcGFn",
        "ZSByb20gcGF0Y2ggc2F2ZSBtYXNrIHBhZ2UgYWRkIHplbGRhIHNhdmUgc3JhbSBydW4gc25hcCBzYXZlIHdpbmRvdyBk",
        "dW1wIG1hc2sgc2xvdCByb20gc2F2ZSB0YWJsZSBzbG90IHplbGRhIHdpbmRvdyBwYXRjaCBzbmFwIHNuYXAgdGFibGUg",
        "cGF0Y2ggd2luZG93IGZsYXNoIHJvbSBwYXRjaCBzcmFtIHJ1biB3aW5kb3cgYWRkIHNuYXAgc2xvdCBzbG90IGZsYXNo",
        "IGZsYXNoIHplbGRhIHNyYW0gcGF0Y2ggcGF0Y2ggdGFibGUgZmxhc2ggc3JhbSBwYWdlIHdpbmRvdyBhZGQgY29weSBj",
        "b3B5IHJvbSBwYWdlIGNvcHkgZmxhc2ggcm9tIHNsb3QgZHVtcCB0YWJsZSBwYWdlIHBhdGNoIHJ1biBydW4gemVsZGEg",
        "c2xvdCByb20gemVsZGEgemVsZGEgbWFzayBmbGFzaCBhZGQgZmxhc2ggZHVtcCBjb3B5IGZsYXNoIHplbGRhIHNsb3Qg",
        "emVsZGEgd2luZG93IGNvcHkgYWRkIHBhdGNoIHJ1biBwYWdlIHBhZ2UgZmxhc2ggc2F2ZSBwYWdlIHNsb3Qgcm9tIHJv",
        "bSBkdW1wIHNuYXAgcGF0Y2ggZmxhc2ggemVsZGEgd2luZG93IHNhdmUgcGF0Y2ggdGFibGUgcGFnZSBydW4gcnVuIHpl",
        "bGRhIHNhdmUgbWFzayBwYXRjaCBtYXNrIHBhdGNoIHNhdmUgcm9tIGZsYXNoIHBhdGNoIG1hc2sgc3JhbSB6ZWxkYSBy",
        "b20gYWRkIHNhdmUgc25hcCBhZGQgcm9tIHJvbSBjb3B5IHplbGRhIHplbGRhIHNyYW0gdGFibGUgZHVtcCB0YWJsZSBw",
        "YXRjaCBzbG90IHdpbmRvdyBzcmFtIHdpbmRvdyBzbG90IHdpbmRvdyBzbG90IHJ1biBzcmFtIGFkZCBzbG90IHBhdGNo",
        "IHNhdmUgZHVtcCB3aW5kb3cgY29weSBtYXNrIHNsb3QgY29weSBtYXNrIGZsYXNoIHNuYXAgcGFnZSBjb3B5IHNsb3Qg",
        "YWRkIGR1bXAgbWFzayBwYXRjaCBzbmFwIGNvcHkgc2F2ZSBhZGQgd2luZG93IHBhZ2Ugd2luZG93IGNvcHkgdGFibGUg",
        "bWFzayByb20gd2luZG93IHJvbSB3aW5kb3cgZmxhc2ggc3JhbSB0YWJsZSBhZGQgZHVtcCBzYXZlIHNsb3Qgcm9tIHNh",
        "dmUgc3JhbSBhZGQgdGFibGUgc3JhbSB6ZWxkYSByb20gY29weSBjb3B5IHNhdmUgcnVuIHNhdmUgc3JhbSBkdW1wIGR1",
        "bXAgZHVtcCBzbmFwIHBhdGNoIHBhZ2UgY29weSBtYXNrIHJ1biBwYXRjaCBzYXZlIHNyYW0gc2F2ZSBzbG90IHplbGRh",
        "IHJ1biByb20gYWRkIGZsYXNoIHJ1biBzbG90IHNsb3QgcGFnZSBydW4gYWRkIHRhYmxlIG1hc2sgemVsZGEgd2luZG93",
        "IHNsb3QgdGFibGUgc25hcCBzYXZlIHJ1biBhZGQgZHVtcCB6ZWxkYSBydW4gcGF0Y2ggY29weSBmbGFzaCBzbG90IG1h",
        "c2sgc2xvdCBzYXZlIGFkZCBydW4gcm9tIHBhZ2UgcGF0Y2ggdGFibGUgcnVuIHJ1biBwYWdlIHplbGRhIGR1bXAgc3Jh",
        "bSB0YWJsZSBzcmFtIHJ1biB6ZWxkYSBzYXZlIHRhYmxlIGNvcHkgc25hcCBzcmFtIG1hc2sgcm9tIG1hc2sgc2F2ZSBz",
        "bmFwIGNvcHkgd2luZG93IHNuYXAgcGF0Y2ggc2F2ZSB3aW5kb3cgcGF0Y2ggY29weSB0YWJsZSBjb3B5IHNyYW0gcGF0",
        "Y2ggcm9tIHdpbmRvdyBzbG90IHJvbSBjb3B5IGR1bXAgYWRkIHNsb3QgYWRkIGR1bXAgd2luZG93IG1hc2sgcm9tIHBh",
        "dGNoIHBhdGNoIHNhdmUgemVsZGEgcm9tIHJ1biBmbGFzaCBzYXZlIHplbGRhIHBhZ2Ugc3JhbSBhZGQgcGF0Y2ggc2xv",
        "dCBkdW1wIHJvbSBhZGQgd2luZG93IGR1bXAgYWRkIGZsYXNoIHJ1biBwYXRjaCBhZGQgYWRkIHplbGRhIHJvbSBkdW1w",
        "IHBhdGNoIHNhdmUgcm9tIHdpbmRvdyBzYXZlIHBhZ2UgY29weSBwYWdlIHNuYXAgcGFnZSBtYXNrIGFkZCBkdW1wIHNu",
        "YXAgc2xvdCByb20gdGFibGUgc2F2ZSBhZGQgcnVuIHdpbmRvdyBzYXZlIHdpbmRvdyBjb3B5IG1hc2sgcGF0Y2ggd2lu",
        "ZG93IHJvbSByb20gc25hcCBzYXZlIHdpbmRvdyBzbG90IHBhZ2Ugcm9tIHplbGRhIHJ1biBmbGFzaCBtYXNrIHBhZ2Ug",
        "c25hcCB0YWJsZSBzbmFwIHJ1biBjb3B5IHNsb3QgcGF0Y2ggZmxhc2ggcGFnZSBtYXNrIHNhdmUgc25hcCBzcmFtIHJv",
        "bSB6ZWxkYSB3aW5kb3cgbWFzayBzYXZlIHNyYW0gYWRkIGR1bXAgZHVtcCBzbmFwIHdpbmRvdyB3aW5kb3cgY29weSBz",
        "YXZlIGFkZCBzYXZlIGFkZCBzbmFwIHNhdmUgcnVuIHdpbmRvdyBkdW1wIGR1bXAgbWFzayBwYXRjaCBjb3B5IHRhYmxl",
        "IHBhdGNoIHBhZ2Ugc25hcCB3aW5kb3cgdGFibGUgemVsZGEgcGFnZSBzbG90IHNuYXAgemVsZGEgc2xvdCB3aW5kb3cg",
        "cGFnZSB0YWJsZSBzbmFwIHNyYW0gcGF0Y2ggemVsZGEgYWRkIHBhdGNoIHBhdGNoIGZsYXNoIG1hc2sgc2F2ZSBzcmFt",
        "IHNhdmUgc2xvdCBzbmFwIHNsb3QgemVsZGEgc3JhbSBkdW1wIHplbGRhIHNuYXAgZmxhc2ggZmxhc2ggYWRkIHBhdGNo",
        "IGR1bXAgcGF0Y2ggc2xvdCB6ZWxkYSB3aW5kb3cgc25hcCB6ZWxkYSBzYXZlIGR1bXAgcm9tIGR1bXAgbWFzayByb20g",
        "c2xvdCBzbmFwIHBhZ2Ugd2luZG93IHdpbmRvdyBkdW1wIGR1bXAgcnVuIHNyYW0gbWFzayBydW4gc2xvdCBkdW1wIGFk",
        "ZCBwYWdlIHNhdmUgYWRkIHJvbSBzbmFwIHNyYW0gZHVtcCBydW4gbWFzayBzYXZlIGNvcHkgc2F2ZSBwYWdlIHNyYW0g",
        "c2F2ZSBydW4gc25hcCBmbGFzaCBwYWdlIHNhdmUgcGF0Y2ggYWRkIHdpbmRvdyBydW4gZmxhc2ggc3JhbSBydW4gd2lu",
        "ZG93IHBhdGNoIHNuYXAgd2luZG93IG1hc2sgc25hcCBjb3B5IHdpbmRvdyBwYWdlIHNuYXAgcGFnZSBzbmFwIHNsb3Qg",
        "cGFnZSBtYXNrIHNhdmUgdGFibGUgcm9tIGR1bXAgemVsZGEgc2xvdCBmbGFzaCByb20gYWRkIGR1bXAgZmxhc2ggdGFi",
        "bGUgbWFzayBzbmFwIGFkZCByb20gcm9tIG1hc2sgc2xvdCBzbmFwIG1hc2sgYWRkIHNyYW0gZmxhc2ggcGFnZSBydW4g",
        "c2xvdCB6ZWxkYSBzYXZlIGR1bXAgc2F2ZSBjb3B5IGR1bXAgYWRkIHNyYW0gZHVtcCB0YWJsZSBzYXZlIHNuYXAgcnVu",
        "IHJ1biBhZGQgYWRkIHBhdGNoIG1hc2sgZmxhc2ggbWFzayBzcmFtIGZsYXNoIHNsb3QgZmxhAgIH6AMAAAUG8WO6p7y5",
        "AZrwCgAABQbN4PX+W1gCEASQCwAA/4AyF7nnYN0B",
    )
)

NSIS_OLDFILE = (
    b"*** THIS IS A TEST FILE FOR THE VPATCH E"
    b"XAMPLE ***\r\n*** COMPILE EXAMPLE.NSI TO T"
    b"EST ***\r\n\r\noldfile - vpatch\r\n\r\n12345 - A"
    b"BCDEF"
)
NSIS_NEWFILE = (
    b"*** THIS IS A TEST FILE FOR THE VPATCH E"
    b"XAMPLE ***\r\n*** COMPILE EXAMPLE.NSI TO T"
    b"EST ***\r\n\r\nnewfile - vpatch\r\n\r\n67890 - G"
    b"HIJKL"
)
NSIS_PATCH = (
    b"VPAT\x01\x00\x00\x80\x03\x00\x00\x00\xdc\xfb+\xd1\x05V\xfc\x8d\xd2\x80\xaf\xa6}j\x14j\xde3=K'\xb8lL\xdf\x8e\x7f\xfa"
    b'\x04\x05\xc3h3\x00\x00\x00\x01[\x00\x00\x00\x00\x05"newfile - vpatch\r\n\r\n6789'
    b"0 - GHIJKL\xff\x00\x83\x17\x82\x8b\x1f\xc3\x01"
)
