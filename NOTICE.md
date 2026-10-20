# Notice

anypatch is written from the specifications and open implementations below. They were read to learn each format; no code, text or test data was copied from them. Reference patches in the test suite were produced by running these programs on synthetic inputs.

| Format | Source | License | How it was used |
|:--|:--|:--|:--|
| IPS, UPS, BPS, APS, PPF, RUP, PMSR, BDF, EBP | [RomPatcher.js](https://github.com/marcrobledo/RomPatcher.js) by Marc Robledo | MIT | Format layouts read; its Node build writes and reads the interop vectors |
| VCDIFF and xdelta3 secondary compression | [RFC 3284](https://www.rfc-editor.org/rfc/rfc3284), [xdelta3](https://github.com/jmacd/xdelta) by Joshua MacDonald | RFC; Apache-2.0 | Format and the DJW and FGK coders read; xdelta3 3.0.11 writes the reference vectors |
| IPS32 | The IPS32 parser in the Citron emulator | Not recorded; read only | Header and end marker read; nothing copied |
| BPS | [byuu's BPS specification](https://floating.muncher.se/byuu/bps/bps_spec.html) | Specification | Format read |
| BSDIFF40 | [bsdiff](https://www.daemonology.net/bsdiff/) by Colin Percival | BSD-2-Clause | Format read; bsdiff writes reference vectors |
| IPS, BPS, UPS | [Flips](https://github.com/Alcaro/Flips) by Alcaro | GPL-3.0 | Run as a separate program to exchange patches with anypatch; nothing read into the code |
| PPF 3.0 | ApplyPPF and MakePPF 3.0 by Icarus/Paradox, as kept in [MultiPatch](https://github.com/sappharad/MultiPatch) | Source header permits use | Image type and block check behaviour read; run as separate programs to exchange patches |
| RUP | [NINJA 2.0](https://web.archive.org/web/2007/http://ninja.cinnamonpirate.com/) by Derrick Sobodash: its format specification, ROM conversion notes and PHP source | GPL-2.0 | ROM-type conversions written from the specification and notes, with the GPL source read only; run as a separate program to write the typed reference patch and exchange patches |
| BSDIFF40 | [bsdiff4](https://github.com/ilanschnell/bsdiff4) by Ilan Schnell | BSD-2-Clause | Run as a separate program to exchange patches |
| PAT, FireFlower | The FireFlower format by Kuma, as NINJA 2.0's reader describes it, and the line layout Microsoft `fc /b` prints | GPL-2.0 source read only | Format read; NINJA 2.0 applies the patches anypatch writes |
| BSDIFF43 | [bsdiff](https://github.com/mendsley/bsdiff) by Matthew Endsley, after Colin Percival | BSD-2-Clause | Format read; its `bsdiff` writes the reference vectors and both tools exchange patches with anypatch |
| GDIFF | [Generic Diff Format Specification](https://www.w3.org/TR/NOTE-gdiff-19970901) by Arthur van Hoff and Jonathan Payne; [javaxdelta](https://sourceforge.net/projects/javaxdelta/) 2.0.1 from Maven Central | W3C NOTE; MIT | Format read; javaxdelta 2.0.1 writes the reference vectors and reads anypatch's output |
