from __future__ import annotations

import unittest
from unittest.mock import patch

from robots_agilex_piper.main import app
from typer.testing import CliRunner


class CliTest(unittest.TestCase):
    def test_version_uses_project_metadata_without_running_node(self) -> None:
        with patch("robots_agilex_piper.main._run_node") as run_node:
            result = CliRunner().invoke(app, ["--version"])

        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.output, "agilex-piper 1.1.3\n")
        run_node.assert_not_called()


if __name__ == "__main__":
    unittest.main()
