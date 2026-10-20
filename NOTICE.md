# Notice

anypatch is written from the specifications and open implementations below. They were read to learn each format; no code, text or test data was copied from them. Reference patches in the test suite were produced by running these programs on synthetic inputs.

| Format | Source | License | How it was used |
|:--|:--|:--|:--|
| IPS, UPS, BPS, APS, PPF, RUP, PMSR, BDF, EBP | [RomPatcher.js](https://github.com/marcrobledo/RomPatcher.js) by Marc Robledo | MIT | Format layouts read; its Node build writes and reads the interop vectors |
| VCDIFF and xdelta3 secondary compression | [RFC 3284](https://www.rfc-editor.org/rfc/rfc3284), [xdelta3](https://github.com/jmacd/xdelta) by Joshua MacDonald | RFC; Apache-2.0 | Format and the DJW and FGK coders read; xdelta3 3.0.11 writes the reference vectors |
| IPS32 | The IPS32 parser in the Citron emulator | Not recorded; read only | Header and end marker read; nothing copied |
| BPS | [byuu's BPS specification](https://floating.muncher.se/byuu/bps/bps_spec.html) | Specification | Format read |
| BSDIFF40 | [bsdiff](https://www.daemonology.net/bsdiff/) by Colin Percival | BSD-2-Clause | Format read; bsdiff writes reference vectors |
