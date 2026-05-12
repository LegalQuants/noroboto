from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = REPO_ROOT / "docs"
SCRIPT_PATH = REPO_ROOT / "noroboto.py"


class NorobotoDocsCorpusTest(unittest.TestCase):
    def test_cli_accepts_all_docs_samples(self) -> None:
        docx_paths = sorted(DOCS_DIR.glob("*.docx"))
        self.assertTrue(docx_paths, f"No .docx files found in {DOCS_DIR}")

        with tempfile.TemporaryDirectory() as temp_root:
            tmp_dir = Path(temp_root) / "tmp"
            tmp_dir.mkdir()

            for input_path in docx_paths:
                output_path = tmp_dir / f"{input_path.stem}-noroboto.docx"
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