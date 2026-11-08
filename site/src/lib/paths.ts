import fs from "node:fs";
import path from "node:path";

function findRoot(): string {
  let dir = process.cwd();
  for (let i = 0; i < 5; i++) {
    if (fs.existsSync(path.join(dir, "pxart.py"))) return dir;
    dir = path.dirname(dir);
  }
  throw new Error("can't find the pxart repository (pxart.py) above " + process.cwd());
}

export const REPO_ROOT = findRoot();
export const REPO = "thethirdbearsolutions/pxart";
export const GITHUB = `https://github.com/${REPO}`;
export const GITHUB_BLOB = `${GITHUB}/blob/main/`;
export const GITHUB_TREE = `${GITHUB}/tree/main/`;
