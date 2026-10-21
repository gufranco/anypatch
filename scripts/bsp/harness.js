const fs = require("fs");
const [library, patchPath, sourcePath, outPath, ...choices] = process.argv.slice(2);
eval(fs.readFileSync(library, "utf-8"));
const toBuffer = (path) => new Uint8Array(fs.readFileSync(path)).buffer;
const patch = new BSPPatcher(toBuffer(patchPath), toBuffer(sourcePath));
patch.print = (text) => { console.log(text); patch.run(); };
patch.menu = (entries) => {
  if (choices.length === 0) { console.log("menu without a choice: " + entries.join(" | ")); process.exitCode = 4; return; }
  patch.run(Number(choices.shift()));
};
patch.error = (error) => { console.log("Error: " + error); process.exitCode = 1; };
patch.failure = (status) => { console.log("exit status " + status); process.exitCode = 2; };
patch.success = (data) => fs.writeFileSync(outPath, Buffer.from(data));
patch.run();
