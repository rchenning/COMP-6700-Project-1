import unittest
import os
import tempfile
import json
from unittest.mock import patch, MagicMock
import pandas as pd
from extractor.executor import (
    load_comparison_files,
    determine_differences_and_map,
    execute_kubescape,
    generate_csv
)

class TestExecutor(unittest.TestCase):

    def test_load_comparison_files(self):
        # Create temp files
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f1:
            f1.write("Names in file1 but not in file2:\ntest1")
            names_file = f1.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f2:
            f2.write("KDEs in file1: test, requirements: []")
            full_file = f2.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f3:
            f3.write("Log content")
            log_file = f3.name

        try:
            files = load_comparison_files(names_file, full_file, log_file)
            self.assertIn("names", files)
            self.assertIn("full", files)
            self.assertIn("log", files)
            self.assertEqual(files["names"], "Names in file1 but not in file2:\ntest1")
        finally:
            os.unlink(names_file)
            os.unlink(full_file)
            os.unlink(log_file)

    @patch('extractor.executor.run_llm_batch')
    def test_determine_differences_and_map_no_differences(self, mock_llm):
        names_content = "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
        full_content = "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"

        output_file = determine_differences_and_map(names_content, full_content)
        self.assertTrue(os.path.exists(output_file))
        with open(output_file, 'r') as f:
            content = f.read().strip()
            self.assertEqual(content, "NO DIFFERENCES FOUND")
        os.unlink(output_file)

    @patch('extractor.executor.run_llm_batch')
    def test_determine_differences_and_map_with_differences(self, mock_llm):
        mock_llm.return_value = ["control1\ncontrol2"]
        names_content = "Names in file1: test1"
        full_content = "KDEs in file1: test, requirements: [req]"

        output_file = determine_differences_and_map(names_content, full_content)
        self.assertTrue(os.path.exists(output_file))
        with open(output_file, 'r') as f:
            content = f.read().strip()
            self.assertIn("control1", content)
        os.unlink(output_file)

    @patch('subprocess.run')
    @patch('zipfile.ZipFile')
    def test_execute_kubescape(self, mock_zip, mock_subprocess):
        # Mock zipfile
        mock_zip.return_value.__enter__.return_value.extractall = MagicMock()
        # Mock kubescape output
        mock_output = {
            "controls": [
                {
                    "severity": "high",
                    "name": "test_control",
                    "failedResources": 5,
                    "allResources": 10,
                    "complianceScore": 50
                }
            ]
        }
        mock_subprocess.return_value = MagicMock(returncode=0, stdout=json.dumps(mock_output))

        # Create temp files
        with tempfile.NamedTemporaryFile(suffix='.zip', delete=False) as zip_f:
            zip_path = zip_f.name
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as ctrl_f:
            ctrl_f.write("control1")
            ctrl_file = ctrl_f.name

        try:
            df = execute_kubescape(ctrl_file, zip_path)
            self.assertIsInstance(df, pd.DataFrame)
            self.assertEqual(len(df), 1)
            self.assertEqual(df.iloc[0]["Control name"], "test_control")
        finally:
            os.unlink(zip_path)
            os.unlink(ctrl_file)

    def test_generate_csv(self):
        df = pd.DataFrame({
            "FilePath": ["path1"],
            "Severity": ["high"],
            "Control name": ["control1"],
            "Failed resources": [5],
            "All Resources": [10],
            "Compliance score": [50]
        })
        output_csv = generate_csv(df)
        self.assertTrue(os.path.exists(output_csv))
        loaded_df = pd.read_csv(output_csv)
        self.assertEqual(len(loaded_df), 1)
        os.unlink(output_csv)

if __name__ == '__main__':
    unittest.main()