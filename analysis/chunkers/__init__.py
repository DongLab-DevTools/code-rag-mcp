from analysis.chunkers.base import CodeChunk
from analysis.chunkers.android import chunk_kotlin, chunk_java
from analysis.chunkers.ios import chunk_swift
from analysis.chunkers.common import (
    CONFIG_FILE_NAMES, WHOLE_FILE_EXTENSIONS, chunk_whole_file,
    chunk_markdown, chunk_plaintext,
    get_res_dir_name, is_values_dir, is_whole_file_res_dir,
    chunk_resource_xml_by_item, chunk_resource_xml_whole,
)
