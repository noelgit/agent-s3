import tempfile
import shutil

from agent_s3.tools.index_partition_manager import IndexPartitionManager


def test_partition_selection_and_optimization():
    tmpdir = tempfile.mkdtemp(prefix="idx_mgr_test_")
    try:
        mgr = IndexPartitionManager(tmpdir)
        py_id = mgr.create_partition({"language": "python"})
        js_id = mgr.create_partition({"language": "javascript"})

        mgr.add_or_update_file("a.py", [0.1, 0.1], {"language": "python"})
        mgr.add_or_update_file("b.py", [0.1, 0.1], {"language": "python"})
        mgr.add_or_update_file("c.py", [0.1, 0.1], {"language": "python"})
        mgr.add_or_update_file("d.js", [0.1, 0.1], {"language": "javascript"})
        mgr.commit_all()

        sel_py = mgr.select_partitions_for_query("python search")
        assert py_id in sel_py and js_id not in sel_py

        sel_js = mgr.select_partitions_for_query("console.log")
        assert js_id in sel_js and py_id not in sel_js

        stats_before = mgr.get_partition_stats()
        assert stats_before["total_files"] == 4

        mgr.optimize_partitions(max_files_per_partition=2)
        stats_after = mgr.get_partition_stats()
        assert stats_after["total_files"] == 4
        for info in stats_after["partitions"].values():
            assert info["file_count"] <= 2
    finally:
        shutil.rmtree(tmpdir)
