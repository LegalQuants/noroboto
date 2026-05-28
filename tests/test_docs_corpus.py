from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
SCRIPT_PATH = REPO_ROOT / "noroboto.py"
SUPPORTED_EXTENSIONS = ("*.docx", "*.pdf")


def _collect_corpus_paths() -> list[Path]:
    collected: list[Path] = []
    for pattern in SUPPORTED_EXTENSIONS:
        collected.extend(sorted(DOCS_DIR.glob(pattern)))
    return collected


class NorobotoDocsCorpusTest(unittest.TestCase):
    def test_cli_accepts_all_docs_samples(self) -> None:
        input_paths = _collect_corpus_paths()
        if not input_paths:
            self.skipTest(f"No .docx or .pdf files found in {DOCS_DIR}")

        with tempfile.TemporaryDirectory() as temp_root:
            tmp_dir = Path(temp_root) / "tmp"
            tmp_dir.mkdir()

            for input_path in input_paths:
                output_path = tmp_dir / f"{input_path.stem}-noroboto{input_path.suffix.lower()}"
                command = [sys.executable, str(SCRIPT_PATH), str(input_path), str(output_path)]
                completed = subprocess.run(
                    command,
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )

                with self.subTest(document=input_path.name):
                    self.assertEqual(
                        completed.returncode,
                        0,
                        "\n".join(
                            [
                                f"CLI rejected {input_path.name}",
                                f"command: {' '.join(command)}",
                                f"stdout: {completed.stdout.strip()}",
                                f"stderr: {completed.stderr.strip()}",
                            ]
                        ),
                    )
                    self.assertTrue(output_path.exists(), f"No output written for {input_path.name}")
                    self.assertGreater(output_path.stat().st_size, 0, f"Empty output written for {input_path.name}")


if __name__ == "__main__":
    unittest.main()
