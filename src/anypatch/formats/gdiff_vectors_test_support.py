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
            "0f/R/wT6AAAByAjUKInDr5lrIPoB0AG8FEjjjrZt4HNyYW0gY29weSB6ZWxk+QOgfhJ6+Hzqd8MgY29weSB3aW5kb3f6",
            "BDAGagYHPXf3unz6CqACTBQOhgy9Dr1oIHBhZ2UgY29weSBjb/oNAAKDDUCa+vEYoGUgZmxhc2j6D5ABLASF0PJS+RDA",
            "0BAnEAPXky50YWJsZSBzbG90+RGgvhK0Vf7k1ucgc2F2ZSB0YWJsZSD6EnACRwnts4DdNAt5IHL6FMAE0BCBQBCwywRw",
            "YXRjaCBwYXRj+hmgAoMNm8sHylF2bXAgcGF0Y/ocMAMQAA==",
        )
    ),
    "grow": _decoded(
        (
            "0f/R/wT6AAAfQF5tYXNrIHBhZ2UgYWRkIHJvbSBjb3B5IHNhdmUgc3JhbSBydW4gdGFibGUgY29weSBzbG90IHNyYW0g",
            "cGFnZSBwYWdlIGR1bXAgY29weSBzcmFtIHdpbmRvdyB6ZWxk+QOgE81mbGFzaCBzbG90IGFkZCBydW4gcGFnZSBwYWdl",
            "IGNvcHkgY29weSBmbGFzaCB6ZWxkYSBtYXNrIGZsYXNoIHJ1biBzYXZlIHBhdGNoIHdpbmRvdyBydW4gemVsZGEgcm9t",
            "IGR1bXAgcnVuIHBhdGNoIGR1bXAgZHVtcCBhZGQgc2F2ZSBzYXZlIHdpbmRvdyBwYWdlIHJvbSB3aW5kb3cgcnVuIHdp",
            "bmRvdyBkdW1wIHNsb3Qgc25hcCB6ZWxkYSBydW4gc2F2ZSBwYWdl+Q9AEhZkdW1wIHBhZ2UgZmxhc2ggc3JhbSB0+Q4w",
            "EfcBHnNhdmUgemVsZGEgZHVtcCBmbGFzaCBtYXNrIHNsb3Qgd2luZG93IGR1bXAgc2xvdCBzbG90IGNvcHkgcGFnZSBz",
            "bG90IHNuYXAgYWRkIGFkZCBydW4gc2F2ZSBtYXNrIHNsb3QgemVsZGEgc25hcCBzbmFwIHNyYW0gY29weSByb20gc3Jh",
            "bSBzYXZlIGR1bXAgdGFibGUgZmxhc2ggdGFibGUgc25hcCBhZGQgcnVuIHdpbmRvdyB0YWJsZSBwYXRjaCBzbmFwIHNs",
            "b3QgdGFibGUgcGF0Y2ggcnVuIGR1bXAgZHVtcCB0YWJsZSBydW4gbWFzayB0YWJsZSB3aW5kb3cgcnVuIGR1bXAgbWFz",
            "ayB6ZWxkYSB3aW5kb3f5ETAQenRhYmxlIHJvbSBwYXRjaCBwYWdlIHJvbSBkdW1wIGR1bXAgcm9tIHJvbSBwYWdlIHNu",
            "YXAgemVsZGEgcnVuIHRhYmxlIGNvcHkgc25hcCBmbGFzaCB0YWJsZSBzbG90IHBhdGNoIHJvbSBydW4gcnVuIHJvbSBw",
            "YWdl+QIwEQVwYWdlIPkVcBF2cGFnZSBkdW1wIGNvcHkgemVsZGEgY29weSBzbmFwIGR1bXAgemVsZGEgcm9tIHJ1biBw",
            "YXRjaCBhZGQgcm9tIHplbGRhIHBhZ2Ugcm9tIGR1bXAgZHVtcCB3aW5kb3cgcGFnZSBwYXRjaCB3aW5kb3cgc2xvdPkI",
            "8BADd2lu+QZQETdjb3B5IHdpbmRvdyBhZGQgdGFibGUgcm9tIG1hc2sgZHVtcCBydW4gZHVtcCBwYWdlIHNuYXAg+QKw",
            "EVxkdW1wIHRhYmxlIHNhdmUgYWRkIGR1bXAgc3JhbSBmbGFzaCBtYXNrIHJvbSB6ZWxkYSByb20gYWRkIHNhdmUgc2xv",
            "dCBzYXZlIGFkZCBwYWdlIHJ1biBwYWdlIPkCcBBMc2F2ZSBwYWdlIHNyYW0gcGFnZSBzbG90IHdpbmRvdyB0YWJsZSBz",
            "cmFtIHRhYmxlIGFkZCBzcmFtIHNsb3QgbWFzayBtYXNrIGFkZPkPgBHaZHVtcCBmbGFzaCB6ZWxkYSBzbG90IGZsYXNo",
            "IHNhdmUgc25hcCBwYXRjaCBzcmFtIHNsb3Qgc2xvdCBjb3B5IHBhdGNoIHBhZ2Ugc2F2ZSBtYXNrIHNuYXAgZmxhc2gg",
            "Zmxhc2ggY29weSBmbGFzaCBhZGQgcnVuIGFkZCBhZGQgd2luZG93IHNuYXAgemVsZGEgbWFzayBzcmFtIG1hc2sgcnVu",
            "IHNuYXAgc3JhbSB0YWJsZSBhZGQgc2F2ZSBkdW1wIGR1bXAgd2luZG93IGZsYXNoIGNvcHn5GjAQPHJ1biBydW4gYWRk",
            "IHJvbSBzcmFtIHJvbSBhZGQgemVsZGEgc2xvdCBhZGQgd2luZG93IHJvbSBzbG90IPkQIBUqbWFzayBkdW1wIGR1bXAg",
            "Zmxhc2ggbWFzayBwYWdlIHBhZ2Ugc25hcCB3+RaQEW1zcmFtIGR1bXAgcm9tIHNsb3QgYWRkIHRhYmxlIHdpbmRvdyBm",
            "bGFzaCBhZGQgYWRkIHJvbSBhZGQgcGF0Y2ggc25hcCBzcmFtIHNyYW0gdGFibGUgc2F2ZSBtYXNrIHBhZ2UgcnVuIGR1",
            "bXAg+QkAERpkdW1wIGNvcHkgc2xvdCByb20gemVsZGEgdPkZQBBdcnVuIHNyYW0gZHVtcCBzbmFwIGR1bXAgd2luZG93",
            "IHNyYW0gcGF0Y2ggcnVuIHJ1biBhZGQgcGF0Y2ggc25hcCByb20gcGF0Y2ggcm9tIG1hc2sgc25hcCBzbG90+RpwFFJw",
            "YWdlIHBhdGNoIGZsYXNoIHNyYW0gc25hcCBtYXNrIHBhZ2UgYWRkIHJ1biBzcmFtIHJ1biB6ZWxkYSBwYXRjaCB6ZWxk",
            "YSB0YWJsZSBzbG90+QQwEPcA/nJ1biBzYXZlIGNvcHkgcm9tIHNyYW0gbWFzayBzYXZlIHplbGRhIGZsYXNoIHBhdGNo",
            "IHNuYXAgemVsZGEgc25hcCBkdW1wIHRhYmxlIHJvbSB3aW5kb3cgd2luZG93IG1hc2sgemVsZGEgc25hcCBydW4gY29w",
            "eSBwYWdlIGFkZCBydW4gZmxhc2ggc2F2ZSBjb3B5IHplbGRhIGFkZCBydW4gc2F2ZSBkdW1wIHNuYXAgbWFzayB3aW5k",
            "b3cgc2F2ZSBkdW1wIHJvbSByb20gc3JhbSBhZGQgc3JhbSBtYXNrIHNsb3QgYWRkIHNhdmUgZmxhc2ggdGFibGUg+Qqw",
            "Ebl6ZWxkYSB0YWJsZSBzcmFtIHJ1biBhZGQgYWRkIHNhdmUgc2F2ZSBwYXRjaCBwYWdlIGNvcHkgbWFzayByb20gdGFi",
            "bGUgcm9tIGNvcHkgYWRkIHdpbmRvdyB3aW5kb3cgZmxhc2ggc2F2ZSBzcmFtIHJ1biB3aW5kb3cgbWFzayBjb3B5IG1h",
            "c2sgcGF0Y2ggZHVtcCBzYXZlIHNuYXAgZHVtcCBydW4gc2F2ZSByb20gc3JhbSBmbPke4BStdGFibGUgcGF0Y2ggdGFi",
            "bGUgc2F2ZSBwYXRjaCB3aW5kb3cgc25hcCBhZGQgemVsZGEgcnVuIHNyYW0gZHVtcCBjb3B5IGNvcHkgcm9tIHdpbmRv",
            "dyBhZGQgcGF0Y2ggcm9tIHNhdmUgdGFibGUgbWFzayB6ZWxkYSBydW4gc2F2ZSBtYXNrIHRhYmxlIHJ1biBhZGQgcGFn",
            "ZSByb20gcnVuIGNvcHkgY29weSD5HoASjGdlIG1hc2sgdGFibGUgc2xvdCBwYXRjaCBzYXZlIHNuYXAgZmxhc2ggbWFz",
            "ayBmbGFzaCBzcmFtIGFkZCBydW4gZmxhc2ggc25hcCB3aW5kb3cgY29weSBhZGQgcm9tIHNhdmUgdGFibGUgemVsZGEg",
            "YWRkIHJ1biBwYXRjaCBwYXRjaCB3aW5kb3cg+QyAEvkIgBIsd2luZG93IHBhdGNoIGFkZCByb20gY29weSByb20gc2xv",
            "dCBkdW1wIHJvbSD5CXARTnBhZ2UgYWRkIHNuYXAgbWFzayByb20gc25hcCBzbmFwIGFkZCByb20gemVsZGEgcGF0Y2gg",
            "cm9tIHJvbSBzcmFtIG1hc2sgc2F2ZSB6ZQA=",
        )
    ),
    "shrink": _decoded(("0f/R/wT6AAATiAA=",)),
    "moved": _decoded(
        (
            "0f/R/wQLc3JhbSBzYXZlIHD6WzAFbRMZf9pM6qx3IHdpbmRvdyBzbG90+mCwB2oGK8E9oBvd+WggkBAHPXf3unxsYXNo",
            "IG1hc2sg+mjAEUYKx24RP+0gc3Jhbfp6EAU1C79OzHOy1iBzcmFt+n9QCBwMYW2F0PJSaCBzcmFt+R5wEgRhZGQg+Tpw",
            "EvqHoBVXB+2zgN00CyD52cAQAndp+p0QAg8RQJr68Rigb3B5IGNvcHkgc3L6nzAELAkOhgy9Dr0gcm/53iASCXNhdmUg",
            "emVsZPqjgAJOEjIJ0WZvHnNyYW0gcm9tIHJvbfml4IkHOVJlK8RfIPqmcAMGCrcGOK1dlmluZG/6qYAEWwmlxNVZLWVv",
            "dyD5LkAQCHJ1biBhZGQg+aMgEQNtYXP6rhAB6gb4rE9sEfr6sAAJjhLmauwY4MogbWFzayBjb3B5IHL6uaAEDwxESzO6",
            "oE5lbGRhIGP5nlAQ+bDgEQNzcmH5qFASD21hc2sgc3JhbSB0YWJsZfq+AALsFJvLB8pRdmluZG93IHJ1biBydW4g+sEA",
            "AboYnntBk9gkc25hcCBtYXNrIHplJxAD15Mu+UOwEA5yb20gcnVuIHJ1biBkdfrC8BI2CrRV/uTW52FzaCD61TAD2Qbf",
            "IVhSjIn5onAR+tkgAecJ1CiJw6+ZIHBh+tsQBB8RxpdhOAYXb3cgc25hcCBtYXP530D3CFol8QudEXZl+UMQEg9zYXZl",
            "IHNhdmUgcGF0Y2j64GAKmgZ6+Hzqd8P66wAVAg6MOt4/qPRsZSBjb3B5IPwAAQAQXwZ+qLa0/3L5DoAQC3JvbSBzYXZl",
            "IHJv/QABAJAB+gZsZ1NfzkH9AAECkA7g+gAAAf0HhfFKeVOzcPmZoBMBcPlsYBADYWRk+Z2AFAFy+gJACKoG8WO6p7y5",
            "+QrwmgbN4PX+W1j6C5AEPxFS3FxFSdByb20gcnVuIHBhZ/kP4GkHrQ1qHoGmc/oQUASqBkuUyID1j/oVAAwGCnOv6CUj",
            "gm9weSD6IRADFAxkHr+aegF3aW5kb3f6JDAhcwyTgnME/DVwYXRjaCD5mNAR+kXABNMN//TjMmU7bSBkdW1wIPpKoAVU",
            "DNjZw403SCBwYXRjaPpQAAiUCxE2RoaWa2ZsYXNo+aqgEAFj+liwAnX8AAEEsBEEZHVtcPlvkBMIYWRkIHJvbSD59DAR",
            "A3JvbfmY4BoHYXZlIGFkZPk/0BAEcm9tIPlzUBEPc25hcCBzbG90IG1hc2sg+QQQFQFm+aUgEBN3aW5kb3cgZHVtcCBz",
            "bmFwIHpl+WmgEQZjb3B5IHP5SAAUBHJvbSD5jRARGnRhYmxlIHNyYW0gZHVtcCB0YWJsZSBzYXZl+UegEDlhdmUgYWRk",
            "IG1hc2sgdGFibGUgYWRkIGR1bXAgemVsZGEgc3JhbSBzbG90IHNsb3QgZmxhc2ggZHX5KsAUAWb56UAQA21hc/k9EBEM",
            "cGFnZSBzYXZlIHdp+aewEw1tYXNrIHJ1biBzYXZl+eoAEAZmbGFzaCD50yAUEmdlIGR1bXAgcnVuIHplbGRhIPkuQBBD",
            "c2xvdCByb20gbWFzayBzbmFwIHplbGRhIHBhdGNoIGNvcHkgcGFnZSBhZGQgc3JhbSBydW4gcnVuIHplbGRhIHJ1bvms",
            "kBAEc25hcPlT4BAEc2xvdPnoABAMcGF0Y2ggcnVuIGZs+YzAEwVkdW1wIPmlYBUEYWRkIPmTEBIEcnVuIPkkcBEEcGFn",
            "ZfmroBAEcGFnZfktUBEuYWRkIHNuYXAgcm9tIHNyYW0gcm9tIHNuYXAgc25hcCB0YWJsZSBhZGQgbWFza/m98BEKY29w",
            "eSBzcmFtIPlUABD5GgARCXBhZ2UgZmxhc/ktoBJ1c25hcCBhZGQgc3JhbSBmbGFzaCBtYXNrIHJ1biBtYXNrIHNuYXAg",
            "bWFzayBydW4gbWFzayBzbG90IHNhdmUgZmxhc2ggc3JhbSBzYXZlIHBhdGNoIGFkZCBzbG90IHNuYXAgc2xvdCB3aW5k",
            "b3cgc2F2ZSBk+QCQEw1yb20gdGFibGUgcm9t+Q0QEhR0YWJsZSBzYXZlIHJ1biBzbG90IPmFABMFZmxhc2j5UUAQPGFk",
            "ZCBmbGFzaCBzYXZlIGR1bXAgdGFibGUgY29weSBzYXZlIHNuYXAgc2xvdCBwYXRjaCByb20gcGFnZfkkkBAbZHVtcCB3",
            "aW5kb3cgc3JhbSBkdW1wIHJvbSBw+RZQEARhdmUg+YmAEAFm+SEgEBdyYW0gbWFzayBwYWdlIHBhZ2Ugc2F2ZfwAAQnA",
            "EARkdW1w+dswEQ1tYXNrIHNyYW0gc3Jh+fwwEvnfABFhZmxhc2ggZmxhc2ggc2xvdCBkdW1wIHNsb3Qgcm9tIHBhZ2Ug",
            "dGFibGUgcm9tIHplbGRhIHNsb3Qgc2xvdCBtYXNrIHNuYXAgc2F2ZSBtYXNrIGFkZCBtYXNrIGNvcHkgc/mBkBIgbWFz",
            "ayB3aW5kb3cgcGFnZSBtYXNrIHRhYmxlIG1hc2v5CoAQBXNsb3Qg+YmAEBhyb20gc25hcCBmbGFzaCBjb3B5IHBhZ2X5",
            "nHARF3JvbSBtYXNrIHJ1biBmbGFzaCBzcmFt+e6QEBFjb3B5IHplbGRhIHJ1biBhZPl8oBEGd2luZG93+eFQERxwYWdl",
            "IG1hc2sgd2luZG93IHNhdmUgc3JhbSBm+XzgEAV6ZWxkYfmYoBAJc25hcCBtYXNr+U3QEBRwYWdlIHNuYXAgdGFibGUg",
            "Y29wefmQEBUKcnVuIHdpbmRvd/wAAQKwEwlwYWdlIGNvcHn5oxAQCWR1bXAgc2xvdPmMoBAKd2luZG93IGFkZPn9MBH5",
            "n/AQGHBhZ2Ugc25hcCBwYWdlIG1hc2sgc2xvdPlWsBMfYWRkIHNuYXAgcGFnZSBmbGFzaCB6ZWxkYSBydW4gZvl7cBEN",
            "c2F2ZSB6ZWxkYSBwYfmMQBIJbWFzayBwYWdl+cTwEB5zcmFtIHJ1biBzbmFwIHNhdmUgd2luZG93IGR1bXD54pAUBnRh",
            "YmxlIPkgIBIJcGF0Y2ggc25h/AABDmATAXf5xKAQBHBhdGP5oJASD2FkZCBzbmFwIHNsb3Qgc/lb0BD5c1AR+UuQEgRz",
            "cmFt+dVwERpjb3B5IGNvcHkgcm9tIHBhZ2UgY29weSBmbPlScBIQdGFibGUgcGFnZSBwYXRjaPlOkBATbG90IHJvbSB6",
            "ZWxkYSB6ZWxkYfkrUBAGZmxhc2gg+Z0gEAZ6ZWxkYSD5ICASCmNvcHkgYWRkIHD5jaAQGmdlIGZsYXNoIHNhdmUgcGFn",
            "ZSBzbG90IHJv+eNAEAZwYXRjaCD5bwATAXP5zwAQBHBhZ2X5TpAQAmF2+exgEglwYXRjaCBzYXb5QtAYD3JhbSB6ZWxk",
            "YSByb20gYfnysBUFcm9tIGP5nlAQBnNyYW0gdPmPMBsDd2lu+YfgEARzbG90+RqAEQRzcmFt+XGwFRVkdW1wIHdpbmRv",
            "dyBjb3B5IG1hc2v5E9AQI2ZsYXNoIHNuYXAgcGFnZSBjb3B5IHNsb3QgYWRkIGR1bXAg+Z+wEAVjb3B5IPmXABABcPmN",
            "QBAHdGFibGUgbfklgBAKb20gd2luZG93IPlXsBERYWRkIGR1bXAgc2F2ZSBzbG/5rtAQEGFkZCB0YWJsZSBzcmFtIHr5",
            "dkATA3Nhdvk7cBD8AAEL4BAnbmFwIHBhdGNoIHBhZ2UgY29weSBtYXNrIHJ1biBwYXRjaCBzYXZl+fsgFzB1biByb20g",
            "YWRkIGZsYXNoIHJ1biBzbG90IHNsb3QgcGFnZSBydW4gYWRkIHRhYmz5dgAZ+bHgEBJydW4gYWRkIGR1bXAgemVsZGH5",
            "7mAQMWZsYXNoIHNsb3QgbWFzayBzbG90IHNhdmUgYWRkIHJ1biByb20gcGFnZSBwYXRjaCD5tCATC3plbGRhIGR1bXAg",
            "+ZbQEARydW4g+TNQESFjb3B5IHNuYXAgc3JhbSBtYXNrIHJvbSBtYXNrIHNhdmX5xtASBHNuYXD5gLATCHBhdGNoIGNv",
            "+ehgEwVwYXRjaPwAAQ6QESZyb20gY29weSBkdW1wIGFkZCBzbG90IGFkZCBkdW1wIHdpbmRvd/laYBYUc2F2ZSB6ZWxk",
            "YSByb20gcnVuIGb5pcAQIHBhZ2Ugc3JhbSBhZGQgcGF0Y2ggc2xvdCBkdW1wIHJv+X+AEhthZGQgZmxhc2ggcnVuIHBh",
            "dGNoIGFkZCBhZGT5SpAQBnBhdGNoIPnvYBAJc2F2ZSBwYWdl+biQEBlwYWdlIG1hc2sgYWRkIGR1bXAgc25hcCBz+cjg",
            "EwlhZGQgcnVuIHf55pASBWNvcHkg+SMAEhdyb20gcm9tIHNuYXAgc2F2ZSB3aW5kb/kr0BAPemVsZGEgcnVuIGZsYXNo",
            "+emgEA90YWJsZSBzbmFwIHJ1biD5XXAQL2ZsYXNoIHBhZ2UgbWFzayBzYXZlIHNuYXAgc3JhbSByb20gemVsZGEgd2lu",
            "ZG93+dRAEBJhZGQgZHVtcCBkdW1wIHNuYXD8AAEDkBQhc2F2ZSBhZGQgc2F2ZSBhZGQgc25hcCBzYXZlIHJ1biB3+X1A",
            "EBBtYXNrIHBhdGNoIGNvcHkg+WHgEQFz+dngEfkOEBAEc25hcPlBoBMEcGFnZfmk0BH5AmAQBnBhdGNoIPmLEBEEc2F2",
            "Zfn7IBAPc25hcCBzbG90IHplbGRh+TRgEQFz+Y5wEAphZGQgcGF0Y2gg+WzwEAJ6ZfnKIBA0emVsZGEgc2F2ZSBkdW1w",
            "IHJvbSBkdW1wIG1hc2sgcm9tIHNsb3Qgc25hcCBwYWdlIHdpbvle8BAOZHVtcCBydW4gc3JhbSD5CEATA2FkZPmBUBAa",
            "b20gc25hcCBzcmFtIGR1bXAgcnVuIG1hc2v51qAQDnBhZ2Ugc3JhbSBzYXZl+fuAEA9wYWdlIHNhdmUgcGF0Y2j5DUAQ",
            "BGZsYXP5oJASEXBhdGNoIHNuYXAgd2luZG93+ROgEAZ3aW5kb3f5UQAQE3NuYXAgc2xvdCBwYWdlIG1hc2v5tmAQE2R1",
            "bXAgemVsZGEgc2xvdCBmbGH5i8AQIWZsYXNoIHRhYmxlIG1hc2sgc25hcCBhZGQgcm9tIHJvbfnkMBAJbWFzayBhZGQg",
            "+faAEBNydW4gc2xvdCB6ZWxkYSBzYXZl+UEQEDRkdW1wIGFkZCBzcmFtIGR1bXAgdGFibGUgc2F2ZSBzbmFwIHJ1biBy",
            "dW4gYWRkIGFkZCBw+YHQEPm3ABANc2xvdCBmbGFvbSByb/m+oBgGZHVtcCB6+dIgEAVtYXNrIPoEIAbKBvFjuqe8ufkK",
            "8JoGzeD1/ltY+guQBBAA",
        )
    ),
}
