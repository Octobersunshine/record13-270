import os
import shutil
import tempfile
from pathlib import Path

from batch_renamer import BatchRenamer, RenameOperation


def create_test_files(directory: Path, filenames):
    for name in filenames:
        (directory / name).touch()


def test_basic_sequential_rename():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt", "b.txt", "c.txt"])

        renamer = BatchRenamer(directory=str(tmp_path))
        ops = renamer.plan()

        assert len(ops) == 3
        assert ops[0].target.name == "file_01.txt"
        assert ops[1].target.name == "file_02.txt"
        assert ops[2].target.name == "file_03.txt"
        print("✓ test_basic_sequential_rename  passed")


def test_custom_base_name_and_padding():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["x.jpg", "y.jpg"])

        renamer = BatchRenamer(
            directory=str(tmp_path),
            base_name="photo",
            index_padding=3,
            start_index=10,
        )
        ops = renamer.plan()

        assert ops[0].target.name == "photo_010.jpg"
        assert ops[1].target.name == "photo_011.jpg"
        print("✓ test_custom_base_name_and_padding  passed")


def test_prefix_and_suffix():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["old.txt"])

        renamer = BatchRenamer(
            directory=str(tmp_path),
            prefix="backup",
            suffix="final",
        )
        ops = renamer.plan()

        assert ops[0].target.name == "backup_file_01_final.txt"
        print("✓ test_prefix_and_suffix  passed")


def test_extension_filter():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt", "b.jpg", "c.txt", "d.png"])

        renamer = BatchRenamer(directory=str(tmp_path), extension="txt")
        ops = renamer.plan()

        assert len(ops) == 2
        assert all(op.target.suffix == ".txt" for op in ops)
        print("✓ test_extension_filter  passed")


def test_alpha_index_format():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, [f"f{i:02d}.txt" for i in range(1, 28)])

        renamer = BatchRenamer(directory=str(tmp_path), index_format="alpha")
        ops = renamer.plan()

        assert ops[0].target.name == "file_a.txt"
        assert ops[1].target.name == "file_b.txt"
        assert ops[25].target.name == "file_z.txt"
        assert ops[26].target.name == "file_aa.txt"
        print("✓ test_alpha_index_format  passed")


def test_uppercase_alpha_index_format():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["1.txt", "2.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), index_format="ALPHA")
        ops = renamer.plan()

        assert ops[0].target.name == "file_A.txt"
        assert ops[1].target.name == "file_B.txt"
        print("✓ test_uppercase_alpha_index_format  passed")


def test_execute_dry_run():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt", "b.txt"])

        original_files = set(p.name for p in tmp_path.iterdir())

        renamer = BatchRenamer(directory=str(tmp_path))
        renamer.execute(dry_run=True)

        after_files = set(p.name for p in tmp_path.iterdir())
        assert original_files == after_files
        print("✓ test_execute_dry_run  passed")


def test_execute_actual_rename():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["apple.txt", "banana.txt"])

        renamer = BatchRenamer(directory=str(tmp_path))
        renamer.execute(dry_run=False)

        result_files = sorted(p.name for p in tmp_path.iterdir())
        assert result_files == ["file_01.txt", "file_02.txt"]
        print("✓ test_execute_actual_rename  passed")


def test_recursive_mode():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        subdir = tmp_path / "sub"
        subdir.mkdir()
        create_test_files(tmp_path, ["root.txt"])
        create_test_files(subdir, ["nested.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), recursive=True)
        ops = renamer.plan()

        assert len(ops) == 2
        print("✓ test_recursive_mode  passed")


def test_custom_separator():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["test.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), separator="-", prefix="2024")
        ops = renamer.plan()

        assert ops[0].target.name == "2024-file-01.txt"
        print("✓ test_custom_separator  passed")


def test_regex_pattern_match():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["IMG_001.jpg", "IMG_002.jpg", "screenshot.png", "IMG_003.jpg"])

        renamer = BatchRenamer(directory=str(tmp_path), pattern=r"^IMG_")
        ops = renamer.plan()

        assert len(ops) == 3
        print("✓ test_regex_pattern_match  passed")


def test_conflict_resolution():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt", "file_01.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), base_name="file", start_index=1, index_padding=2)
        ops = renamer.plan()

        renamer.execute(dry_run=False)

        result_files = sorted(p.name for p in tmp_path.iterdir())
        assert result_files == ["file_01.txt", "file_02.txt"]
        print("✓ test_conflict_resolution  passed")


def test_invalid_directory():
    try:
        BatchRenamer(directory="/nonexistent/path/that/will/never/exist")
        assert False, "应该抛出 ValueError"
    except ValueError:
        print("✓ test_invalid_directory  passed")


def test_existing_target_file_auto_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["photo.jpg", "file_01.jpg"])

        renamer = BatchRenamer(directory=str(tmp_path), base_name="file", start_index=1, index_padding=2, extension="jpg")
        ops = renamer.plan()

        assert len(ops) == 1
        assert ops[0].source.name == "photo.jpg"
        assert ops[0].target.name == "file_01_1.jpg"
        print("✓ test_existing_target_file_auto_dedup  passed")


def test_multiple_existing_targets_dedup():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(
            tmp_path,
            ["apple.txt", "banana.txt", "cherry.txt", "file_01.txt", "file_02.txt", "file_02_1.txt"],
        )

        renamer = BatchRenamer(
            directory=str(tmp_path),
            base_name="file",
            start_index=1,
            index_padding=2,
            pattern=r"^(apple|banana|cherry)\.txt$",
        )
        ops = renamer.plan()

        target_names = sorted(op.target.name for op in ops)
        assert target_names == ["file_01_1.txt", "file_02_2.txt", "file_03.txt"]
        print("✓ test_multiple_existing_targets_dedup  passed")


def test_execute_with_existing_target_no_error():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["photo_a.jpg", "photo_b.jpg", "file_01.jpg"])

        renamer = BatchRenamer(
            directory=str(tmp_path),
            base_name="file",
            start_index=1,
            index_padding=2,
            pattern=r"^photo_",
        )
        renamer.execute(dry_run=False)

        result_files = sorted(p.name for p in tmp_path.iterdir())
        assert "file_01.jpg" in result_files
        assert "file_01_1.jpg" in result_files
        assert "file_02.jpg" in result_files
        print("✓ test_execute_with_existing_target_no_error  passed")


def test_dedup_between_plan_targets():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["z.txt", "y.txt", "x.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), base_name="file", start_index=1, index_padding=2)
        renamer.execute(dry_run=False)

        result_files = sorted(p.name for p in tmp_path.iterdir())
        assert result_files == ["file_01.txt", "file_02.txt", "file_03.txt"]
        print("✓ test_dedup_between_plan_targets  passed")


def test_dedup_preserves_extension():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["photo.png", "file_01.png", "other.jpg"])

        renamer = BatchRenamer(
            directory=str(tmp_path),
            base_name="file",
            start_index=1,
            index_padding=2,
            extension="png",
        )
        ops = renamer.plan()

        assert len(ops) == 1
        assert ops[0].source.name == "photo.png"
        assert ops[0].target.name == "file_01_1.png"
        print("✓ test_dedup_preserves_extension  passed")


def test_preview_returns_list_of_dicts():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt", "b.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), base_name="doc", index_padding=3)
        result = renamer.preview()

        assert isinstance(result, list)
        assert len(result) == 2
        assert "source_name" in result[0]
        assert "target_name" in result[0]
        assert "source_path" in result[0]
        assert "target_path" in result[0]
        assert result[0]["source_name"] == "a.txt"
        assert result[0]["target_name"] == "doc_001.txt"
        assert result[1]["source_name"] == "b.txt"
        assert result[1]["target_name"] == "doc_002.txt"
        print("✓ test_preview_returns_list_of_dicts  passed")


def test_format_preview_simple_style():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["apple.txt", "banana.txt"])

        renamer = BatchRenamer(directory=str(tmp_path))
        output = renamer.format_preview(table_style="simple")

        assert "源文件" in output
        assert "目标文件" in output
        assert "apple.txt" in output
        assert "banana.txt" in output
        assert "file_01.txt" in output
        assert "file_02.txt" in output
        assert "->" in output
        print("✓ test_format_preview_simple_style  passed")


def test_format_preview_markdown_style():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["x.jpg", "y.jpg"])

        renamer = BatchRenamer(directory=str(tmp_path))
        output = renamer.format_preview(table_style="markdown")

        assert "| # | 源文件 | 目标文件 |" in output
        assert "|---|--------|----------|" in output
        assert "| 1 | x.jpg | file_01.jpg |" in output
        assert "| 2 | y.jpg | file_02.jpg |" in output
        print("✓ test_format_preview_markdown_style  passed")


def test_format_preview_no_index():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt"])

        renamer = BatchRenamer(directory=str(tmp_path))
        output = renamer.format_preview(show_index=False, table_style="simple")

        assert "源文件" in output
        assert "目标文件" in output
        assert " 1 " not in output
        print("✓ test_format_preview_no_index  passed")


def test_format_preview_show_path():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["test.txt"])

        renamer = BatchRenamer(directory=str(tmp_path))
        output = renamer.format_preview(show_path=True, table_style="simple")

        assert "test.txt" in output
        assert "file_01.txt" in output
        assert str(tmp_path) in output
        print("✓ test_format_preview_show_path  passed")


def test_format_preview_empty():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["a.txt", "b.txt"])

        renamer = BatchRenamer(directory=str(tmp_path), pattern=r"nonexistent_pattern")
        output = renamer.format_preview()

        assert output == "没有找到需要重命名的文件。"

        renamer2 = BatchRenamer(directory=str(tmp_path), extension="xyz")
        output2 = renamer2.format_preview()
        assert output2 == "没有找到需要重命名的文件。"
        print("✓ test_format_preview_empty  passed")


def test_preview_does_not_modify_files():
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        create_test_files(tmp_path, ["photo.jpg", "image.png"])

        before = sorted(p.name for p in tmp_path.iterdir())

        renamer = BatchRenamer(directory=str(tmp_path))
        renamer.preview()
        renamer.format_preview()

        after = sorted(p.name for p in tmp_path.iterdir())
        assert before == after
        print("✓ test_preview_does_not_modify_files  passed")


def test_rename_operation_to_dict():
    op = RenameOperation(source=Path("/src/old.txt"), target=Path("/src/new.txt"))
    d = op.to_dict()
    assert d["source_name"] == "old.txt"
    assert d["target_name"] == "new.txt"
    assert "old.txt" in d["source_path"]
    assert "new.txt" in d["target_path"]
    print("✓ test_rename_operation_to_dict  passed")


if __name__ == "__main__":
    test_basic_sequential_rename()
    test_custom_base_name_and_padding()
    test_prefix_and_suffix()
    test_extension_filter()
    test_alpha_index_format()
    test_uppercase_alpha_index_format()
    test_execute_dry_run()
    test_execute_actual_rename()
    test_recursive_mode()
    test_custom_separator()
    test_regex_pattern_match()
    test_conflict_resolution()
    test_invalid_directory()
    test_existing_target_file_auto_dedup()
    test_multiple_existing_targets_dedup()
    test_execute_with_existing_target_no_error()
    test_dedup_between_plan_targets()
    test_dedup_preserves_extension()
    test_preview_returns_list_of_dicts()
    test_format_preview_simple_style()
    test_format_preview_markdown_style()
    test_format_preview_no_index()
    test_format_preview_show_path()
    test_format_preview_empty()
    test_preview_does_not_modify_files()
    test_rename_operation_to_dict()
    print("\n🎉 所有测试通过！")
