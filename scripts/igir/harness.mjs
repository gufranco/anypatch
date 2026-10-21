import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const [igirRoot, patchPath, sourcePath, outPath] = process.argv.slice(2);
const load = async (relative) => (await import(path.join(igirRoot, "dist/src", relative))).default;
const File = await load("models/files/file.js");
const PatchFactory = await load("factories/patchFactory.js");

const folder = fs.mkdtempSync(path.join(os.tmpdir(), "igir-"));
const named = path.join(folder, `patch 00000000${path.extname(patchPath)}`);
fs.copyFileSync(patchPath, named);
const patchFile = await File.fileOf({ filePath: named });
const patch =
  (await PatchFactory.patchFromFileContents(patchFile)) ??
  (await PatchFactory.patchFromFilename(patchFile));
if (patch === undefined) {
  console.log("igir does not recognise this patch");
  process.exit(3);
}
const source = await File.fileOf({ filePath: sourcePath });
await patch.createPatchedFile(source, outPath);
fs.rmSync(folder, { recursive: true, force: true });
