from analysis.chunkers.common.config import CONFIG_FILE_NAMES, WHOLE_FILE_EXTENSIONS, chunk_whole_file
from analysis.chunkers.common.document import chunk_markdown, chunk_plaintext
from analysis.chunkers.common.resource import (
    get_res_dir_name, is_values_dir, is_whole_file_res_dir,
    chunk_resource_xml_by_item, chunk_resource_xml_whole,
)
