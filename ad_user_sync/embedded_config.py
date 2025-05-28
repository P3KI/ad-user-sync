import sys

from ad_user_sync.logger import Logger
from ad_user_sync.model.ExportConfig import ExportConfig
from ad_user_sync.model.ImportConfig import InteractiveImportConfig, ImportConfig

class EmbeddedConfig:

    HEADER_EXPORT_START = b"__EMBEDDED_EXPORT_CONFIG_START__"
    HEADER_EXPORT_END   = b"__EMBEDDED_EXPORT_CONFIG_END__"

    HEADER_IMPORT_START = b"__EMBEDDED_IMPORT_CONFIG_START__"
    HEADER_IMPORT_END   = b"__EMBEDDED_IMPORT_CONFIG_END__"


    def __init__(self, logger : Logger):
        self.export_config = None
        self.import_config = None

        if not getattr(sys, 'frozen', False):
            return None


        exec_path = sys.executable
        with open(exec_path, "rb") as f:
            exec_buffer = f.read()

            export_config_buffer = self.get_section(exec_buffer, self.HEADER_EXPORT_START, self.HEADER_EXPORT_END)
            import_config_buffer = self.get_section(exec_buffer, self.HEADER_IMPORT_START, self.HEADER_IMPORT_END)


            if export_config_buffer is not None:
                self.export_config = ExportConfig.deserialize(export_config_buffer)
                if self.export_config is not None:
                    logger.info("Embedded export config found")
                else:
                    logger.warning("Embedded export config not parsable.")

            if import_config_buffer is not None:
                self.import_config = InteractiveImportConfig.deserialize(import_config_buffer) or ImportConfig.deserialize(import_config_buffer)
                if self.import_config is not None:
                    logger.info("Embedded import config found")
                else:
                    logger.warning("Embedded import config not parsable.")

            if export_config_buffer is None and import_config_buffer is None:
                logger.info("No Embedded config found")


    def get_section(self, buffer : bytes, start_mark : bytes, end_mark : bytes) -> str:
        start_index = buffer.find(start_mark)
        if start_index < 0:
            return None

        start_index += len(start_mark)

        end_index = buffer.find(end_mark)
        if end_index < 0:
            return None

        if start_index >= end_index:
            return None

        return buffer[start_index : end_index].decode("utf-8")
