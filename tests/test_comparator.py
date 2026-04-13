import os
import tempfile
import yaml
from extractor.comparator import load_yaml_files, compare_names, compare_full

def test_load_yaml_files():
    # Test with valid files
    data1 = [{'name': 'test1', 'requirements': ['req1']}]
    data2 = [{'name': 'test2', 'requirements': ['req2']}]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
        yaml.dump(data1, f1)
        file1 = f1.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
        yaml.dump(data2, f2)
        file2 = f2.name

    try:
        loaded1, loaded2 = load_yaml_files(file1, file2)
        assert loaded1 == data1
        assert loaded2 == data2
    finally:
        os.unlink(file1)
        os.unlink(file2)

    # Test with non-existent file
    try:
        load_yaml_files('nonexistent.yaml', file2)
        assert False, "Should raise FileNotFoundError"
    except FileNotFoundError:
        pass

def test_compare_names():
    data1 = [{'name': 'kde1', 'requirements': []}, {'name': 'kde2', 'requirements': []}]
    data2 = [{'name': 'kde1', 'requirements': []}, {'name': 'kde3', 'requirements': []}]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
        yaml.dump(data1, f1)
        file1 = f1.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
        yaml.dump(data2, f2)
        file2 = f2.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as out:
        output_file = out.name

    try:
        compare_names(file1, file2, output_file)
        with open(output_file, 'r') as f:
            content = f.read().strip()
        expected = "Names in file1 but not in file2:\nkde2\n\nNames in file2 but not in file1:\nkde3"
        assert content == expected
    finally:
        os.unlink(file1)
        os.unlink(file2)
        os.unlink(output_file)

    # Test no differences
    data3 = [{'name': 'kde1', 'requirements': []}]
    data4 = [{'name': 'kde1', 'requirements': []}]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f3:
        yaml.dump(data3, f3)
        file3 = f3.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f4:
        yaml.dump(data4, f4)
        file4 = f4.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as out2:
        output_file2 = out2.name

    try:
        compare_names(file3, file4, output_file2)
        with open(output_file2, 'r') as f:
            content = f.read().strip()
        assert content == "NO DIFFERENCES IN REGARDS TO ELEMENT NAMES"
    finally:
        os.unlink(file3)
        os.unlink(file4)
        os.unlink(output_file2)

def test_compare_full():
    data1 = [{'name': 'kde1', 'requirements': ['req1']}, {'name': 'kde2', 'requirements': ['req2']}]
    data2 = [{'name': 'kde1', 'requirements': ['req1']}, {'name': 'kde3', 'requirements': ['req3']}]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f1:
        yaml.dump(data1, f1)
        file1 = f1.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f2:
        yaml.dump(data2, f2)
        file2 = f2.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as out:
        output_file = out.name

    try:
        compare_full(file1, file2, output_file)
        with open(output_file, 'r') as f:
            content = f.read()
        # Should have sections for file1 and file2
        assert "KDEs in file1 but not in file2 or with different requirements:" in content
        assert "KDEs in file2 but not in file1 or with different requirements:" in content
        assert "file1: kde2," in content
        assert "file2: kde3," in content
    finally:
        os.unlink(file1)
        os.unlink(file2)
        os.unlink(output_file)

    # Test no differences
    data3 = [{'name': 'kde1', 'requirements': ['req1']}]
    data4 = [{'name': 'kde1', 'requirements': ['req1']}]

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f3:
        yaml.dump(data3, f3)
        file3 = f3.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f4:
        yaml.dump(data4, f4)
        file4 = f4.name
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as out2:
        output_file2 = out2.name

    try:
        compare_full(file3, file4, output_file2)
        with open(output_file2, 'r') as f:
            content = f.read().strip()
        assert content == "NO DIFFERENCES IN REGARDS TO ELEMENT REQUIREMENTS"
    finally:
        os.unlink(file3)
        os.unlink(file4)
        os.unlink(output_file2)