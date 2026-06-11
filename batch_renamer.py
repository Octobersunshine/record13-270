import os
import re
import argparse
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Callable


@dataclass
class RenameOperation:
    source: Path
    target: Path

    def __str__(self):
        return f"{self.source.name}  ->  {self.target.name}"


class BatchRenamer:
    def __init__(
        self,
        directory: str,
        prefix: str = "",
        suffix: str = "",
        start_index: int = 1,
        index_padding: int = 2,
        index_format: str = "num",
        base_name: str = "file",
        pattern: Optional[str] = None,
        extension: Optional[str] = None,
        recursive: bool = False,
        separator: str = "_",
    ):
        self.directory = Path(directory).resolve()
        if not self.directory.is_dir():
            raise ValueError(f"目录不存在: {self.directory}")

        self.prefix = prefix
        self.suffix = suffix
        self.start_index = start_index
        self.index_padding = index_padding
        self.index_format = index_format
        self.base_name = base_name
        self.pattern = re.compile(pattern) if pattern else None
        self.extension = extension.lower().lstrip(".") if extension else None
        self.recursive = recursive
        self.separator = separator

    def collect_files(self) -> List[Path]:
        files: List[Path] = []
        iterator = self.directory.rglob("*") if self.recursive else self.directory.iterdir()

        for entry in iterator:
            if not entry.is_file():
                continue
            if self.pattern and not self.pattern.search(entry.name):
                continue
            if self.extension and entry.suffix.lower().lstrip(".") != self.extension:
                continue
            files.append(entry)

        files.sort(key=lambda p: p.name.lower())
        return files

    def _format_index(self, index: int) -> str:
        if self.index_format == "num":
            return str(index).zfill(self.index_padding)
        elif self.index_format == "alpha":
            return self._num_to_alpha(index)
        elif self.index_format == "ALPHA":
            return self._num_to_alpha(index).upper()
        else:
            raise ValueError(f"不支持的序号格式: {self.index_format}")

    @staticmethod
    def _num_to_alpha(n: int) -> str:
        result = ""
        n -= 1
        while True:
            result = chr(n % 26 + ord("a")) + result
            n = n // 26 - 1
            if n < 0:
                break
        return result

    def generate_new_name(self, original: Path, index: int) -> Path:
        ext = original.suffix
        idx_str = self._format_index(index)

        name_parts = []
        if self.prefix:
            name_parts.append(self.prefix)

        name_parts.append(self.base_name)

        name_parts.append(idx_str)

        if self.suffix:
            name_parts.append(self.suffix)

        new_stem = self.separator.join(part for part in name_parts if part)
        new_name = new_stem + ext
        return original.parent / new_name

    def plan(self) -> List[RenameOperation]:
        files = self.collect_files()
        operations: List[RenameOperation] = []
        current_index = self.start_index

        for file_path in files:
            new_path = self.generate_new_name(file_path, current_index)
            if new_path != file_path:
                operations.append(RenameOperation(source=file_path, target=new_path))
            current_index += 1

        return operations

    @staticmethod
    def _resolve_conflicts(operations: List[RenameOperation]) -> List[RenameOperation]:
        target_paths = {op.target for op in operations}
        source_paths = {op.source for op in operations}
        conflicts = target_paths & source_paths

        if not conflicts:
            return operations

        resolved: List[RenameOperation] = []
        temp_suffix = ".__rename_temp__"

        intermediate_ops: List[RenameOperation] = []
        final_ops: List[RenameOperation] = []

        for op in operations:
            if op.source in conflicts:
                temp_path = op.source.parent / (op.source.name + temp_suffix)
                intermediate_ops.append(RenameOperation(source=op.source, target=temp_path))
                final_ops.append(RenameOperation(source=temp_path, target=op.target))
            else:
                resolved.append(op)

        resolved = intermediate_ops + resolved + final_ops
        return resolved

    def execute(
        self,
        dry_run: bool = False,
        progress_callback: Optional[Callable[[RenameOperation, int, int], None]] = None,
    ) -> List[RenameOperation]:
        operations = self.plan()
        if not operations:
            return []

        operations = self._resolve_conflicts(operations)
        total = len(operations)

        for i, op in enumerate(operations, 1):
            if progress_callback:
                progress_callback(op, i, total)

            if dry_run:
                continue

            if op.target.exists():
                raise FileExistsError(f"目标文件已存在: {op.target}")

            op.source.rename(op.target)

        return operations


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="文件批量重命名工具 - 支持添加前缀/后缀、按序号重命名",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 按序号重命名 (file_01.txt, file_02.txt, ...)
  python batch_renamer.py /path/to/dir

  # 自定义基础名和序号位数 (doc_001.pdf, doc_002.pdf, ...)
  python batch_renamer.py /path/to/dir -b doc -p 3

  # 添加前缀和后缀 (backup_file_01_final.txt)
  python batch_renamer.py /path/to/dir --prefix backup --suffix final

  # 只处理 .jpg 文件，从 100 开始编号
  python batch_renamer.py /path/to/dir -e jpg -s 100

  # 使用字母序号 (file_a.txt, file_b.txt, ...)
  python batch_renamer.py /path/to/dir -f alpha

  # 预览模式（不实际重命名）
  python batch_renamer.py /path/to/dir -n
        """,
    )

    parser.add_argument("directory", help="目标目录路径")

    parser.add_argument("-b", "--base-name", default="file", help="基础文件名 (默认: file)")
    parser.add_argument("-s", "--start", type=int, default=1, help="起始序号 (默认: 1)")
    parser.add_argument("-p", "--padding", type=int, default=2, help="序号补零位数 (默认: 2)")
    parser.add_argument(
        "-f",
        "--format",
        choices=["num", "alpha", "ALPHA"],
        default="num",
        help="序号格式: num=数字, alpha=小写字母, ALPHA=大写字母 (默认: num)",
    )

    parser.add_argument("--prefix", default="", help="添加前缀")
    parser.add_argument("--suffix", default="", help="添加后缀")
    parser.add_argument("--sep", default="_", help="各部分分隔符 (默认: _)")

    parser.add_argument("-e", "--extension", help="只处理指定扩展名的文件 (如: txt)")
    parser.add_argument("-m", "--match", help="按正则表达式匹配文件名")
    parser.add_argument("-r", "--recursive", action="store_true", help="递归处理子目录")

    parser.add_argument("-n", "--dry-run", action="store_true", help="预览模式，不实际重命名")
    parser.add_argument("-q", "--quiet", action="store_true", help="静默模式，减少输出")

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    try:
        renamer = BatchRenamer(
            directory=args.directory,
            prefix=args.prefix,
            suffix=args.suffix,
            start_index=args.start,
            index_padding=args.padding,
            index_format=args.format,
            base_name=args.base_name,
            pattern=args.match,
            extension=args.extension,
            recursive=args.recursive,
            separator=args.sep,
        )
    except ValueError as e:
        print(f"错误: {e}")
        return 1

    operations = renamer.plan()
    if not operations:
        print("没有找到需要重命名的文件。")
        return 0

    if not args.quiet:
        mode = "【预览模式】" if args.dry_run else "【执行模式】"
        print(f"{mode} 将重命名 {len(operations)} 个文件:\n")
        for i, op in enumerate(operations, 1):
            print(f"  {i:>3}. {op}")
        print()

    if args.dry_run:
        print("预览完毕，未对文件进行任何修改。")
        return 0

    try:
        def progress(op: RenameOperation, current: int, total: int):
            if not args.quiet:
                print(f"[{current}/{total}] {op}")

        renamer.execute(dry_run=False, progress_callback=progress)
        print(f"\n完成！成功重命名 {len(operations)} 个文件。")
    except (FileExistsError, OSError) as e:
        print(f"\n错误: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
